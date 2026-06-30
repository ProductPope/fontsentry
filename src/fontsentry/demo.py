"""Offline demo wiring: a filesystem-backed httpx transport and demo config.

The demo runs the real scan pipeline against static files under ``demo/sites/``,
served by a MockTransport that maps ``https://<host>/<path>`` to a file on disk.
No network, no private data — one command produces a meaningful report.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from fontsentry.models import (
    CacheSettings,
    CrawlSettings,
    Settings,
    Target,
)

_CONTENT_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".xml": "application/xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def demo_dir() -> Path:
    return repo_root() / "demo"


def demo_sites_dir() -> Path:
    return demo_dir() / "sites"


def demo_registry_path() -> Path:
    return demo_dir() / "registry" / "licenses.yaml"


def demo_targets() -> list[Target]:
    return [Target(domain="example-demo.test"), Target(domain="example-shop.test")]


def demo_settings() -> Settings:
    return Settings(
        crawl=CrawlSettings(
            respect_robots=False,
            discover_subdomains=True,
            per_host_rate_limit=1000.0,
            max_depth=1,
            max_pages_per_domain=10,
        ),
        cache=CacheSettings(enabled=False),
    )


def local_transport(sites_dir: Path) -> httpx.MockTransport:
    """A transport that serves files from ``sites_dir/<host>/<path>``."""

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        if path.endswith("/"):
            path += "index.html"
        target = sites_dir / host / path.lstrip("/")
        if not target.is_file():
            return httpx.Response(404, text="not found")
        content_type = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        return httpx.Response(
            200, content=target.read_bytes(), headers={"content-type": content_type}
        )

    return httpx.MockTransport(handler)


def demo_client(sites_dir: Path | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=local_transport(sites_dir or demo_sites_dir()))
