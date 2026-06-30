"""Async fetcher with bounded concurrency, per-host rate limiting, cache + robots.

The fetcher owns the politeness policy. It returns a :class:`FetchResult` for any
completed HTTP response (including 4xx/5xx so callers can react), and ``None`` only
when a request is disallowed by robots.txt or fails at the transport level.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from fontsentry.crawl.cache import HttpCache
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
    ) -> None:
        self._client = client
        self._settings = settings
        self._cache = cache
        self._robots = robots
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

    async def fetch(self, url: str) -> FetchResult | None:
        if self._settings.respect_robots and self._robots is not None:
            if not await self._robots.allowed(url):
                return None
            extra_delay = await self._robots.crawl_delay(url)
        else:
            extra_delay = None

        await self._throttle(self._host(url), extra_delay)

        headers = {"User-Agent": self._settings.user_agent}
        if self._cache is not None:
            headers.update(self._cache.conditional_headers(url))

        async with self._semaphore:
            try:
                response = await self._client.get(
                    url,
                    headers=headers,
                    timeout=self._settings.request_timeout,
                    follow_redirects=True,
                )
            except httpx.HTTPError:
                return None

        return self._handle(url, response)

    def _handle(self, url: str, response: httpx.Response) -> FetchResult:
        if response.status_code == 304 and self._cache is not None:
            cached = self._cache.load(url)
            if cached is not None:
                return FetchResult(
                    url=url,
                    status=cached.status,
                    content=cached.content,
                    content_type=cached.content_type,
                    from_cache=True,
                )

        content = response.content
        content_type = response.headers.get("content-type", "")
        if response.status_code == 200 and content and self._cache is not None:
            self._cache.store(
                url,
                status=200,
                content=content,
                content_type=content_type,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            )

        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            content=content,
            content_type=content_type,
        )
