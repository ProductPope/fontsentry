"""Async fetcher with bounded concurrency, per-host rate limiting, cache + robots.

The fetcher owns the politeness policy. It returns a :class:`FetchResult` for any
completed HTTP response (including 4xx/5xx so callers can react), and ``None`` only
when a request is disallowed by robots.txt or fails at the transport level.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from fontsentry.crawl.cache import HttpCache
from fontsentry.crawl.netguard import Resolver, is_safe_host
from fontsentry.crawl.robots import RobotsManager
from fontsentry.models import CrawlSettings


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content: bytes
    content_type: str
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.from_cache or 200 <= self.status < 300


class Fetcher:
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: CrawlSettings,
        *,
        cache: HttpCache | None = None,
        robots: RobotsManager | None = None,
        host_resolver: Resolver = socket.getaddrinfo,
    ) -> None:
        self._client = client
        self._settings = settings
        self._cache = cache
        self._robots = robots
        self._resolver = host_resolver
        self._semaphore = asyncio.Semaphore(settings.concurrency)
        self._base_interval = 1.0 / settings.per_host_rate_limit
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._host_last: dict[str, float] = {}

    @staticmethod
    def _host(url: str) -> str:
        return urlsplit(url).netloc.lower()

    async def _throttle(self, host: str, extra_delay: float | None) -> None:
        interval = self._base_interval
        if extra_delay is not None:
            interval = max(interval, extra_delay)
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            wait = interval - (loop.time() - self._host_last.get(host, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._host_last[host] = loop.time()

    def _host_safe(self, url: str) -> bool:
        if not self._settings.block_private_hosts:
            return True
        return is_safe_host(urlsplit(url).hostname or "", resolver=self._resolver)

    async def _read_capped(self, response: httpx.Response) -> bytes | None:
        # Reject on a declared over-cap Content-Length, then enforce the cap while
        # streaming so a compressed body can't inflate past it in memory.
        cap = self._settings.max_response_bytes
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > cap:
            return None
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > cap:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    async def fetch(self, url: str) -> FetchResult | None:
        # Follow redirects manually so every hop is SSRF-checked and size-capped;
        # httpx auto-redirects would bypass both. The conditional-cache headers and
        # the cache entry stay keyed on the original url (only sent on the 1st hop).
        current = url
        for hop in range(self._settings.max_redirects + 1):
            if not self._host_safe(current):
                return None
            if self._settings.respect_robots and self._robots is not None:
                if not await self._robots.allowed(current):
                    return None
                extra_delay = await self._robots.crawl_delay(current)
            else:
                extra_delay = None
            await self._throttle(self._host(current), extra_delay)

            headers = {"User-Agent": self._settings.user_agent}
            if hop == 0 and self._cache is not None:
                headers.update(self._cache.conditional_headers(url))

            try:
                async with self._semaphore:  # noqa: SIM117 — inner ctx needs its own body
                    async with self._client.stream(
                        "GET",
                        current,
                        headers=headers,
                        timeout=self._settings.request_timeout,
                        follow_redirects=False,
                    ) as response:
                        location = response.headers.get("location")
                        if response.is_redirect and location:
                            current = urljoin(current, location)
                            continue
                        if response.status_code == 304 and hop == 0 and self._cache is not None:
                            cached = self._cache.load(url)
                            if cached is not None:
                                return FetchResult(
                                    url=url,
                                    status=cached.status,
                                    content=cached.content,
                                    content_type=cached.content_type,
                                    from_cache=True,
                                )
                        content = await self._read_capped(response)
                        if content is None:
                            return None
                        content_type = response.headers.get("content-type", "")
                        etag = response.headers.get("etag")
                        last_modified = response.headers.get("last-modified")
                        status = response.status_code
                        final_url = str(response.url)
            except httpx.HTTPError:
                return None

            if status == 200 and content and self._cache is not None:
                self._cache.store(
                    url,
                    status=200,
                    content=content,
                    content_type=content_type,
                    etag=etag,
                    last_modified=last_modified,
                )
            return FetchResult(
                url=final_url, status=status, content=content, content_type=content_type
            )

        return None  # too many redirects
