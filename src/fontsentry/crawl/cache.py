"""A small on-disk HTTP cache keyed by URL, using validators for conditional GETs.

We store the body next to a JSON sidecar holding the ETag / Last-Modified so the
fetcher can revalidate with `If-None-Match` / `If-Modified-Since` and reuse the
body on a 304. This avoids re-downloading unchanged pages and font files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CachedResponse:
    status: int
    content: bytes
    content_type: str
    etag: str | None
    last_modified: str | None


class HttpCache:
    def __init__(self, directory: Path, *, enabled: bool = True) -> None:
        self.directory = directory
        self.enabled = enabled

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _meta_path(self, url: str) -> Path:
        return self.directory / f"{self._key(url)}.json"

    def _body_path(self, url: str) -> Path:
        return self.directory / f"{self._key(url)}.body"

    def load(self, url: str) -> CachedResponse | None:
        if not self.enabled:
            return None
        meta_path = self._meta_path(url)
        body_path = self._body_path(url)
        if not meta_path.exists() or not body_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            content = body_path.read_bytes()
        except (OSError, json.JSONDecodeError):
            return None
        return CachedResponse(
            status=int(meta.get("status", 200)),
            content=content,
            content_type=str(meta.get("content_type", "")),
            etag=meta.get("etag"),
            last_modified=meta.get("last_modified"),
        )

    def store(
        self,
        url: str,
        *,
        status: int,
        content: bytes,
        content_type: str,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        if not self.enabled:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        meta = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "etag": etag,
            "last_modified": last_modified,
        }
        self._meta_path(url).write_text(json.dumps(meta), encoding="utf-8")
        self._body_path(url).write_bytes(content)

    def conditional_headers(self, url: str) -> dict[str, str]:
        cached = self.load(url)
        if cached is None:
            return {}
        headers: dict[str, str] = {}
        if cached.etag:
            headers["If-None-Match"] = cached.etag
        if cached.last_modified:
            headers["If-Modified-Since"] = cached.last_modified
        return headers
