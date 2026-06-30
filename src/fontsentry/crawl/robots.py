"""Per-host robots.txt fetching and policy lookup, cached for the crawl's lifetime.

A missing, unreachable, or unparseable robots.txt is treated as "allow all" — the
polite default for a passive auditor.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import httpx
from protego import Protego


class RobotsManager:
    def __init__(
        self, client: httpx.AsyncClient, user_agent: str, *, timeout: float = 15.0
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._timeout = timeout
        self._cache: dict[str, Protego | None] = {}

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))

    async def _policy(self, url: str) -> Protego | None:
        origin = self._origin(url)
        if origin in self._cache:
            return self._cache[origin]

        policy: Protego | None = None
        try:
            response = await self._client.get(
                f"{origin}/robots.txt", timeout=self._timeout, follow_redirects=True
            )
            if response.status_code == 200 and response.text.strip():
                policy = Protego.parse(response.text)
        except httpx.HTTPError:
            policy = None

        self._cache[origin] = policy
        return policy

    async def allowed(self, url: str) -> bool:
        policy = await self._policy(url)
        if policy is None:
            return True
        return bool(policy.can_fetch(url, self._user_agent))

    async def crawl_delay(self, url: str) -> float | None:
        policy = await self._policy(url)
        if policy is None:
            return None
        delay = policy.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None
