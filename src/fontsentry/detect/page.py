"""Detect every font on a single page: parse HTML/CSS, classify, read metadata.

This is the per-page orchestration that turns fetched bytes into DetectedFont
records. It depends on the crawl Fetcher only through its async ``fetch`` method,
so it works identically over the network and over the demo's local transport.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fontsentry.crawl.fetcher import Fetcher
from fontsentry.detect.css import (
    FontFaceRule,
    FontSource,
    parse_font_faces,
    parse_font_families,
)
from fontsentry.detect.embedding import classify_embedding
from fontsentry.detect.fontfile import FontReadError, read_font_metadata
from fontsentry.detect.html import parse_html
from fontsentry.models import DetectedFont, EmbeddingMethod, FontFormat
from fontsentry.textutil import decode_text

# Preference order when an @font-face lists several sources.
_FORMAT_RANK = {
    FontFormat.WOFF2: 0,
    FontFormat.WOFF: 1,
    FontFormat.OTF: 2,
    FontFormat.TTF: 3,
    FontFormat.EOT: 4,
    FontFormat.UNKNOWN: 5,
}


def _best_source(rule: FontFaceRule) -> FontSource | None:
    if not rule.sources:
        return None
    return min(rule.sources, key=lambda s: _FORMAT_RANK.get(s.font_format, 9))


async def _collect_css(fetcher: Fetcher, page_url: str) -> list[tuple[str, str]]:
    """Return (css_text, base_url) pairs for inline and linked stylesheets."""

    result = await fetcher.fetch(page_url)
    if result is None or not result.ok or "html" not in result.content_type.lower():
        return []

    html = decode_text(result.content, result.content_type)
    assets = parse_html(html, base_url=page_url)

    blocks: list[tuple[str, str]] = [(css, page_url) for css in assets.inline_styles]
    for link in assets.stylesheet_links:
        css = await fetcher.fetch(link)
        if css is not None and css.ok:
            blocks.append((decode_text(css.content, css.content_type), link))
    return blocks


async def detect_page(fetcher: Fetcher, page_url: str) -> list[DetectedFont]:
    """Detect all fonts referenced by a single page."""

    page_host = urlsplit(page_url).netloc
    blocks = await _collect_css(fetcher, page_url)

    face_families: set[str] = set()
    used_families: set[str] = set()
    detected: list[DetectedFont] = []

    # Which families are actually referenced by a font-family usage. Used both to
    # find system fonts (used but no @font-face) and to mark @font-face fonts that
    # are served but not applied to any text.
    for css_text, _base in blocks:
        used_families.update(parse_font_families(css_text))
    used_lower = {u.lower() for u in used_families}

    for css_text, base_url in blocks:
        for rule in parse_font_faces(css_text, base_url=base_url):
            face_families.add(rule.family.lower())
            applied = rule.family.lower() in used_lower
            detected.append(await _detect_face(fetcher, rule, page_url, page_host, applied))

    for family in used_families:
        if family.lower() not in face_families:
            detected.append(
                DetectedFont(
                    family=family,
                    embedding=EmbeddingMethod.SYSTEM,
                    font_format=FontFormat.UNKNOWN,
                    source_page=page_url,
                )
            )

    return detected


async def _detect_face(
    fetcher: Fetcher, rule: FontFaceRule, page_url: str, page_host: str, applied: bool
) -> DetectedFont:
    source = _best_source(rule)
    font_url = source.url if source else None
    fmt = source.font_format if source else FontFormat.UNKNOWN
    embedding = classify_embedding(font_url, page_host)

    metadata = None
    if font_url:
        fetched = await fetcher.fetch(font_url)
        if fetched is not None and fetched.ok and fetched.content:
            try:
                metadata, file_format = read_font_metadata(fetched.content)
                if fmt is FontFormat.UNKNOWN:
                    fmt = file_format
            except FontReadError:
                metadata = None

    return DetectedFont(
        family=rule.family,
        embedding=embedding,
        font_format=fmt,
        source_page=page_url,
        font_url=font_url,
        metadata=metadata,
        applied=applied,
    )
