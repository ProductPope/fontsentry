"""Crawl layer: cache, fetcher (robots/304/errors), and passive discovery.

All offline via httpx.MockTransport — no live network.
"""

from __future__ import annotations

import asyncio
import ipaddress
from pathlib import Path
from typing import Any

import httpx

from fontsentry.crawl.cache import HttpCache
from fontsentry.crawl.ct import ct_subdomains
from fontsentry.crawl.discovery import (
    discover_pages,
    extract_links,
    is_sitemap_index,
    parse_sitemap,
)
from fontsentry.crawl.fetcher import Fetcher
from fontsentry.crawl.robots import RobotsManager
from fontsentry.models import CrawlSettings, Target

Routes = dict[str, httpx.Response]


def _client(routes: Routes, *, default_status: int = 404) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        response = routes.get(str(request.url))
        if response is None:
            return httpx.Response(default_status, text="not found")
        # Build a fresh response each call so .content can be re-read.
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=response.content,
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _html(body: str) -> httpx.Response:
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/html"})


def _settings(**overrides: object) -> CrawlSettings:
    # block_private_hosts off by default here so offline MockTransport hosts
    # aren't sent through real DNS resolution; SSRF-guard tests opt back in.
    base: dict[str, object] = {
        "per_host_rate_limit": 1000.0,
        "respect_robots": False,
        "block_private_hosts": False,
    }
    base.update(overrides)
    return CrawlSettings(**base)


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path)
    cache.store(
        "https://x/a.css",
        status=200,
        content=b"body{}",
        content_type="text/css",
        etag='"abc"',
        last_modified="Wed, 01 Jan 2026 00:00:00 GMT",
    )
    cached = cache.load("https://x/a.css")
    assert cached is not None
    assert cached.content == b"body{}"
    assert cache.conditional_headers("https://x/a.css") == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": "Wed, 01 Jan 2026 00:00:00 GMT",
    }


def test_cache_disabled_is_noop(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path, enabled=False)
    cache.store(
        "https://x", status=200, content=b"x", content_type="", etag=None, last_modified=None
    )
    assert cache.load("https://x") is None
    assert cache.conditional_headers("https://x") == {}


# --------------------------------------------------------------------------- #
# Fetcher
# --------------------------------------------------------------------------- #


async def test_fetch_success() -> None:
    routes = {"https://example.com/": _html("<p>hi</p>")}
    async with _client(routes) as client:
        fetcher = Fetcher(client, _settings())
        result = await fetcher.fetch("https://example.com/")
    assert result is not None and result.ok
    assert b"hi" in result.content


async def test_fetch_404_not_ok() -> None:
    async with _client({}) as client:
        result = await Fetcher(client, _settings()).fetch("https://example.com/missing")
    assert result is not None
    assert result.status == 404
    assert not result.ok


async def test_robots_disallow_returns_none() -> None:
    routes = {
        "https://example.com/robots.txt": httpx.Response(
            200, text="User-agent: *\nDisallow: /private"
        ),
        "https://example.com/private": _html("secret"),
    }
    async with _client(routes) as client:
        settings = _settings(respect_robots=True)
        robots = RobotsManager(client, settings.user_agent)
        fetcher = Fetcher(client, settings, robots=robots)
        assert await fetcher.fetch("https://example.com/private") is None
        assert await fetcher.fetch("https://example.com/public") is not None


def _echo_resolver(host: str, *args: Any, **kwargs: Any) -> list[Any]:
    # IP literals resolve to themselves; hostnames resolve to a public IP.
    try:
        ipaddress.ip_address(host)
        ip = host
    except ValueError:
        ip = "93.184.216.34"
    return [(2, 1, 6, "", (ip, 0))]


async def test_ssrf_guard_blocks_private_target() -> None:
    async with _client({}) as client:
        fetcher = Fetcher(client, _settings(block_private_hosts=True), host_resolver=_echo_resolver)
        assert await fetcher.fetch("http://127.0.0.1/") is None


async def test_ssrf_guard_blocks_redirect_to_private_host() -> None:
    routes = {
        "https://example.com/": httpx.Response(
            302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
        )
    }
    async with _client(routes) as client:
        fetcher = Fetcher(client, _settings(block_private_hosts=True), host_resolver=_echo_resolver)
        # Initial (public) host is fine; the redirect hop to link-local is refused.
        assert await fetcher.fetch("https://example.com/") is None


async def test_response_over_size_cap_is_dropped() -> None:
    routes = {
        "https://example.com/big": httpx.Response(
            200, content=b"A" * 500, headers={"content-type": "text/html"}
        )
    }
    async with _client(routes) as client:
        fetcher = Fetcher(client, _settings(max_response_bytes=100))
        assert await fetcher.fetch("https://example.com/big") is None


async def test_fetcher_semaphore_allows_concurrency() -> None:
    inflight = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0.02)
        inflight -= 1
        return httpx.Response(200, content=b"<p>x</p>", headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = Fetcher(client, _settings(concurrency=5))
        await asyncio.gather(*(fetcher.fetch(f"https://example.com/p{i}") for i in range(5)))
    assert peak >= 2  # requests overlapped rather than running strictly serially


async def test_robots_crawl_delay_and_policy_cached() -> None:
    calls = {"robots": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            calls["robots"] += 1
            return httpx.Response(200, text="User-agent: *\nCrawl-delay: 5")
        return _html("<p>x</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        robots = RobotsManager(client, "FontSentry/test")
        assert await robots.allowed("https://example.com/a") is True
        assert await robots.crawl_delay("https://example.com/a") == 5.0
    assert calls["robots"] == 1  # policy fetched once per origin, then cached


async def test_robots_allow_by_default_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        robots = RobotsManager(client, "FontSentry/test")
        assert await robots.allowed("https://example.com/anything") is True
        assert await robots.crawl_delay("https://example.com/anything") is None


async def test_ct_non_list_json_returns_empty_without_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"error": "nope"})  # valid JSON, wrong shape

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await ct_subdomains(client, "example.com") == []
    assert calls["n"] == 1  # unexpected shape -> no retry


async def test_ct_extracts_and_filters_hosts() -> None:
    rows = [
        {"name_value": "a.example.com\n*.b.example.com"},
        "not-a-dict",
        {"name_value": "example.com"},  # apex excluded
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rows)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await ct_subdomains(client, "example.com") == ["a.example.com", "b.example.com"]


async def test_conditional_304_uses_cache(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path)
    cache.store(
        "https://example.com/a.woff2",
        status=200,
        content=b"FONTDATA",
        content_type="font/woff2",
        etag='"v1"',
        last_modified=None,
    )
    routes = {"https://example.com/a.woff2": httpx.Response(304)}
    async with _client(routes) as client:
        fetcher = Fetcher(client, _settings(), cache=cache)
        result = await fetcher.fetch("https://example.com/a.woff2")
    assert result is not None and result.from_cache
    assert result.content == b"FONTDATA"


# --------------------------------------------------------------------------- #
# Discovery helpers
# --------------------------------------------------------------------------- #


def test_extract_links_absolute_and_filtered() -> None:
    html = (
        '<a href="/about">a</a><a href="https://ext.com/x">b</a>'
        '<a href="mailto:x@y.z">c</a><a href="#frag">d</a>'
    )
    links = extract_links(html, "https://example.com/")
    assert "https://example.com/about" in links
    assert "https://ext.com/x" in links
    assert not any(link.startswith("mailto") for link in links)


def test_parse_sitemap() -> None:
    xml = (
        '<?xml version="1.0"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/p1</loc></url>"
        "<url><loc>https://example.com/p2</loc></url>"
        "</urlset>"
    )
    assert parse_sitemap(xml.encode()) == ["https://example.com/p1", "https://example.com/p2"]


def test_parse_sitemap_malformed() -> None:
    assert parse_sitemap(b"not xml") == []


def test_is_sitemap_index() -> None:
    index = (
        '<?xml version="1.0"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    urlset = "<urlset><url><loc>https://example.com/p</loc></url></urlset>"
    assert is_sitemap_index(index.encode()) is True
    assert is_sitemap_index(urlset.encode()) is False
    assert is_sitemap_index(b"not xml") is False


async def test_discover_follows_sitemap_index() -> None:
    index = (
        '<?xml version="1.0"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    child = (
        '<?xml version="1.0"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/deep-page</loc></url>"
        "</urlset>"
    )
    routes = {
        "https://example.com/": _html("<p>home</p>"),
        "https://example.com/sitemap.xml": httpx.Response(
            200, content=index.encode(), headers={"content-type": "application/xml"}
        ),
        "https://example.com/sitemap-1.xml": httpx.Response(
            200, content=child.encode(), headers={"content-type": "application/xml"}
        ),
        "https://example.com/deep-page": _html("<p>deep</p>"),
    }
    async with _client(routes) as client:
        pages = await discover_pages(
            Fetcher(client, _settings()), Target(domain="example.com"), _settings()
        )
    assert "https://example.com/deep-page" in pages


async def test_redirected_response_is_not_cached(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path)
    routes = {
        "https://example.com/a": httpx.Response(302, headers={"location": "https://example.com/b"}),
        "https://example.com/b": _html("<p>b</p>"),
    }
    async with _client(routes) as client:
        result = await Fetcher(client, _settings(), cache=cache).fetch("https://example.com/a")
    assert result is not None and b"b" in result.content
    # The redirected body must not be cached under the original url.
    assert cache.load("https://example.com/a") is None


# --------------------------------------------------------------------------- #
# Discovery crawl
# --------------------------------------------------------------------------- #


def _discovery_routes() -> Routes:
    return {
        "https://example.com/": _html(
            '<a href="/about">about</a><a href="/contact">contact</a>'
            '<a href="https://external.com/">ext</a>'
            '<a href="https://blog.example.com/">blog</a>'
        ),
        "https://example.com/about": _html("<p>about</p>"),
        "https://example.com/contact": _html("<p>contact</p>"),
        "https://example.com/sitemap.xml": httpx.Response(
            200,
            headers={"content-type": "application/xml"},
            content=(
                b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                b"<url><loc>https://example.com/products</loc></url></urlset>"
            ),
        ),
        "https://example.com/products": _html("<p>products</p>"),
        "https://blog.example.com/": _html("<p>blog home</p>"),
        "https://blog.example.com/sitemap.xml": httpx.Response(404),
    }


async def _discover(target: Target, settings: CrawlSettings) -> set[str]:
    async with _client(_discovery_routes()) as client:
        fetcher = Fetcher(client, settings)
        return set(await discover_pages(fetcher, target, settings))


async def test_discovery_follows_links_and_sitemap_within_domain() -> None:
    pages = await _discover(Target(domain="example.com"), _settings(max_depth=1))
    assert "https://example.com/" in pages
    assert "https://example.com/about" in pages
    assert "https://example.com/products" in pages  # from sitemap
    assert "https://blog.example.com/" in pages  # subdomain discovery on by default
    assert "https://external.com/" not in pages  # external excluded


async def test_discovery_excludes_subdomains_when_disabled() -> None:
    pages = await _discover(
        Target(domain="example.com"), _settings(max_depth=1, discover_subdomains=False)
    )
    assert "https://blog.example.com/" not in pages
    assert "https://example.com/about" in pages


async def test_discovery_respects_depth_zero() -> None:
    pages = await _discover(Target(domain="example.com"), _settings(max_depth=0))
    # Only seeds (homepage + sitemap loc) are fetched; links are not followed.
    assert "https://example.com/" in pages
    assert "https://example.com/products" in pages
    assert "https://example.com/about" not in pages


async def test_discovery_respects_page_cap() -> None:
    pages = await _discover(
        Target(domain="example.com"), _settings(max_depth=2, max_pages_per_domain=2)
    )
    assert len(pages) == 2


async def test_subdomain_seed_is_crawled() -> None:
    target = Target(domain="example.com", subdomain_seeds=["blog.example.com"])
    pages = await _discover(target, _settings(max_depth=0, discover_subdomains=False))
    # Explicit seed is crawled even with subdomain discovery off.
    assert "https://blog.example.com/" in pages
