"""Static bundle scan: recover self-hosted fonts referenced only inside JS bundles.

Single-page apps (Angular, Vue, React, …) wire up their ``@font-face`` at runtime,
so no font is visible in the static HTML/CSS a crawler reads. But the font files'
URLs are still shipped as plain strings inside the app's script bundles. Reading
those bundles statically recovers the fonts — no headless browser, deterministic.

Only same-site bundles are fetched (never third-party analytics scripts). For each
font URL found, the file itself is fetched and its name table read, so the verdict
rests on the font's own metadata — exactly as for a statically-declared font.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from fontsentry.crawl.fetcher import Fetcher
from fontsentry.detect.embedding import _host, _same_site, classify_embedding
from fontsentry.detect.fontfile import FontReadError, read_font_metadata
from fontsentry.detect.html import HtmlAssets
from fontsentry.models import DetectedFont

# Font-file URLs as they appear in a bundle: an absolute http(s) URL, or a
# root-relative path (e.g. ``/assets/fonts/x.woff2``). Bare relative paths are
# skipped — too ambiguous to resolve reliably and prone to false matches.
_FONT_URL_RE = re.compile(
    r"""https?://[^\s"'()]+?\.(?:woff2|woff|ttf|otf|eot)"""
    r"""|/[A-Za-z0-9_./%\-]+\.(?:woff2|woff|ttf|otf|eot)"""
)

# Bound the network fan-out per page.
_MAX_BUNDLES = 20
_MAX_FONT_URLS = 50


def _is_bundle(url: str) -> bool:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith((".js", ".mjs", ".css"))


def _is_own(url: str, page_host: str, own: tuple[str, ...]) -> bool:
    host = _host(url)
    if not host:  # relative -> same origin
        return True
    return _same_site(host, page_host) or any(_same_site(host, o) for o in own if o)


async def detect_bundle_fonts(
    fetcher: Fetcher,
    assets: HtmlAssets,
    page_url: str,
    page_host: str,
    own: tuple[str, ...],
    seen_urls: set[str],
) -> list[DetectedFont]:
    """Scan same-site JS bundles for font-file URLs; fetch and read each font."""

    bundles = [s for s in assets.script_srcs if _is_bundle(s) and _is_own(s, page_host, own)]

    font_urls: list[str] = []
    for src in bundles[:_MAX_BUNDLES]:
        fetched = await fetcher.fetch(src)
        if fetched is None or not fetched.ok or not fetched.content:
            continue
        # Webpack/Vite-style manifests embed URLs JSON-escaped (https:\/\/…);
        # unescape so the regex sees them. A stray non-URL hit costs one 404.
        text = fetched.content.decode("utf-8", "replace").replace("\\/", "/")
        for match in _FONT_URL_RE.findall(text):
            # Root-relative paths belong to the bundle's own host (which may be a
            # declared asset domain), not necessarily the page's.
            url = urljoin(src, match)
            if url in seen_urls or url in font_urls:
                continue
            font_urls.append(url)
            if len(font_urls) >= _MAX_FONT_URLS:
                break
        if len(font_urls) >= _MAX_FONT_URLS:
            break

    out: list[DetectedFont] = []
    for url in font_urls:
        seen_urls.add(url)
        fetched = await fetcher.fetch(url)
        if fetched is None or not fetched.ok or not fetched.content:
            continue
        try:
            metadata, file_format = read_font_metadata(fetched.content)
        except FontReadError:
            continue
        family = (metadata.family_name or "").strip()
        if not family:
            continue
        out.append(
            DetectedFont(
                family=family,
                embedding=classify_embedding(url, page_host, own),
                font_format=file_format,
                source_page=page_url,
                font_url=url,
                metadata=metadata,
            )
        )
    return out
