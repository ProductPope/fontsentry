"""Passive page and subdomain discovery within a target domain.

Sources, all passive: the homepage, sitemap.xml, links observed while crawling,
and an optional seed list of subdomains from config. No brute-force enumeration.
Bounded by ``max_depth`` and ``max_pages_per_domain``.
"""

from __future__ import annotations

from collections import deque
from urllib.parse import urldefrag, urljoin, urlsplit
from xml.etree import ElementTree

from selectolax.parser import HTMLParser

from fontsentry.crawl.fetcher import Fetcher
from fontsentry.models import CrawlSettings, Target


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _is_within(host: str, domain: str, *, follow_subdomains: bool) -> bool:
    host = host.lower()
    domain = domain.lower()
    if host == domain:
        return True
    if host.endswith("." + domain):
        return follow_subdomains
    return False


def extract_links(html: str, base_url: str) -> list[str]:
    """Absolute http(s) links found in a page, with fragments stripped."""

    links: list[str] = []
    for node in HTMLParser(html).css("a"):
        href = node.attributes.get("href")
        if not href:
            continue
        absolute, _frag = urldefrag(urljoin(base_url, href))
        if absolute.startswith(("http://", "https://")):
            links.append(absolute)
    return links


def parse_sitemap(data: bytes) -> list[str]:
    """Return <loc> URLs from a sitemap (or sitemap index); tolerant of errors."""

    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return []
    locs: list[str] = []
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] == "loc" and elem.text:
            locs.append(elem.text.strip())
    return locs


def _is_html(content_type: str) -> bool:
    return "html" in content_type.lower()


async def discover_pages(fetcher: Fetcher, target: Target, settings: CrawlSettings) -> list[str]:
    """Discover crawlable HTML pages for a target, respecting depth and page caps."""

    domain = target.domain
    follow_subs = settings.discover_subdomains

    seeds: list[str] = [f"https://{domain}/"]
    seeds += [f"https://{sub}/" for sub in target.subdomain_seeds]

    sitemap = await fetcher.fetch(f"https://{domain}/sitemap.xml")
    if sitemap is not None and sitemap.ok:
        for loc in parse_sitemap(sitemap.content):
            if _is_within(_host(loc), domain, follow_subdomains=follow_subs):
                seeds.append(loc)

    queue: deque[tuple[str, int]] = deque((url, 0) for url in seeds)
    visited: set[str] = set()
    pages: list[str] = []

    while queue and len(pages) < settings.max_pages_per_domain:
        url, depth = queue.popleft()
        url, _frag = urldefrag(url)
        if url in visited:
            continue
        visited.add(url)

        result = await fetcher.fetch(url)
        if result is None or not result.ok or not _is_html(result.content_type):
            continue

        pages.append(url)

        if depth < settings.max_depth:
            html = result.content.decode("utf-8", errors="replace")
            for link in extract_links(html, url):
                if link not in visited and _is_within(
                    _host(link), domain, follow_subdomains=follow_subs
                ):
                    queue.append((link, depth + 1))

    return pages[: settings.max_pages_per_domain]
