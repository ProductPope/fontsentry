"""Detect every font on a single page: parse HTML/CSS, classify, read metadata.

This is the per-page orchestration that turns fetched bytes into DetectedFont
records. It depends on the crawl Fetcher only through its async ``fetch`` method,
so it works identically over the network and over the demo's local transport.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Iterable
from urllib.parse import unquote_to_bytes, urlsplit

from fontsentry.crawl.fetcher import Fetcher
from fontsentry.detect.bundle import detect_bundle_fonts
from fontsentry.detect.css import (
    FontFaceRule,
    FontSource,
    parse_font_faces,
    parse_font_families,
    parse_imports,
)
from fontsentry.detect.embedding import classify_embedding, host_matches
from fontsentry.detect.fontfile import FontReadError, read_font_metadata
from fontsentry.detect.html import HtmlAssets, parse_html
from fontsentry.models import DetectedFont, EmbeddingMethod, FontFormat
from fontsentry.textutil import decode_text

logger = logging.getLogger(__name__)

# Third-party font-loader scripts: a <script> from one of these delivers fonts at
# runtime (the @font-face is not statically visible), which is a third-party
# privacy fact even when we can't enumerate the individual fonts. Loader host
# (matched exact-or-subdomain, dot-bounded) -> (label, method).
_FONT_LOADERS: tuple[tuple[str, str, EmbeddingMethod], ...] = (
    ("use.typekit.net", "Adobe Fonts (Typekit)", EmbeddingMethod.ADOBE_FONTS),
    ("use.typekit.com", "Adobe Fonts (Typekit)", EmbeddingMethod.ADOBE_FONTS),
    ("p.typekit.net", "Adobe Fonts (Typekit)", EmbeddingMethod.ADOBE_FONTS),
    ("kit.fontawesome.com", "Font Awesome (Kit)", EmbeddingMethod.OTHER_CDN),
    ("cloud.typography.com", "Cloud.typography", EmbeddingMethod.OTHER_CDN),
)

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


# Family names that ship with an OS / are web-safe. A family used in a font-family
# stack with no @font-face and not on this list is UNKNOWN delivery (not SYSTEM) —
# it may be injected by JavaScript or otherwise unobserved, which must not read as
# a clean "system font". Lowercased; generic keywords are filtered earlier in CSS.
_KNOWN_SYSTEM_FAMILIES = frozenset(
    {
        "arial",
        "arial black",
        "helvetica",
        "helvetica neue",
        "times",
        "times new roman",
        "georgia",
        "courier",
        "courier new",
        "verdana",
        "tahoma",
        "trebuchet ms",
        "palatino",
        "palatino linotype",
        "garamond",
        "cambria",
        "calibri",
        "candara",
        "consolas",
        "constantia",
        "corbel",
        "franklin gothic medium",
        "gill sans",
        "lucida grande",
        "lucida sans unicode",
        "segoe ui",
        "segoe ui emoji",
        "apple color emoji",
        "menlo",
        "monaco",
        "sf pro",
        "sf pro text",
        "sf pro display",
        "roboto",  # Android system font
        "noto sans",
        "noto serif",
        "dejavu sans",
        "liberation sans",
        "cantarell",
        "ubuntu",
        "droid sans",
        "impact",
        "comic sans ms",
        "webdings",
        # Synthetic system-fallback names used by the offline demo (brand-neutral
        # stand-ins for real OS fonts).
        "common sans",
        "common serif",
    }
)


# Bound how many stylesheets one page may pull in (linked + transitively imported)
# so an @import cycle or a hostile sheet can't fan out unboundedly.
_MAX_STYLESHEETS = 40

# Bound preload-driven font fetches per page — the one fetch path that had no cap
# (stylesheets, bundles, and bundle font URLs all have one).
_MAX_PRELOADS = 50


async def _collect_css(
    fetcher: Fetcher, page_url: str
) -> tuple[list[tuple[str, str]], HtmlAssets | None]:
    """Return (css_text, base_url) pairs and the page's parsed HTML assets."""

    result = await fetcher.fetch(page_url)
    if result is None or not result.ok or "html" not in result.content_type.lower():
        return [], None

    html = decode_text(result.content, result.content_type)
    assets = parse_html(html, base_url=page_url)

    blocks: list[tuple[str, str]] = [(css, page_url) for css in assets.inline_styles]

    # BFS over stylesheets, following @import (fonts are often delivered through an
    # imported sheet). Dedupe by URL and cap the total to avoid cycles/fan-out.
    seen: set[str] = set()
    queue: list[str] = list(assets.stylesheet_links)
    # inline @imports are relative to the page.
    for css_text in assets.inline_styles:
        queue.extend(parse_imports(css_text, base_url=page_url))

    while queue and len(seen) < _MAX_STYLESHEETS:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        css = await fetcher.fetch(url)
        if css is None or not css.ok:
            continue
        text = decode_text(css.content, css.content_type)
        blocks.append((text, url))
        queue.extend(parse_imports(text, base_url=url))

    return blocks, assets


def _decode_data_uri(url: str) -> bytes | None:
    """Decode `data:[<mime>][;base64],<data>` into bytes (inline-embedded fonts)."""
    if not url.startswith("data:"):
        return None
    header, _, data = url[5:].partition(",")
    if not data:
        return None
    try:
        if ";base64" in header.lower():
            return base64.b64decode(data)
        return unquote_to_bytes(data)
    except (binascii.Error, ValueError):
        return None


async def _font_bytes(fetcher: Fetcher, url: str) -> bytes | None:
    """Get a font's bytes — decoded inline for data: URIs, otherwise fetched."""
    if url.startswith("data:"):
        return _decode_data_uri(url)
    fetched = await fetcher.fetch(url)
    if fetched is not None and fetched.ok and fetched.content:
        return fetched.content
    return None


async def detect_page(
    fetcher: Fetcher, page_url: str, *, own_hosts: Iterable[str] = ()
) -> list[DetectedFont]:
    """Detect all fonts referenced by a single page."""

    page_host = urlsplit(page_url).netloc
    own = tuple(own_hosts)
    blocks, assets = await _collect_css(fetcher, page_url)

    face_families: set[str] = set()
    used_families: set[str] = set()
    detected: list[DetectedFont] = []
    seen_urls: set[str] = set()

    # Which families are actually referenced by a font-family usage. Used both to
    # find system fonts (used but no @font-face) and to mark @font-face fonts that
    # are served but not applied to any text.
    for css_text, _base in blocks:
        used_families.update(parse_font_families(css_text))
    used_lower = {u.lower() for u in used_families}

    for css_text, base_url in blocks:
        for rule in parse_font_faces(css_text, base_url=base_url):
            face_families.add(rule.family.lower())
            # A @font-face with no fetchable url — only `local()` sources (or none) —
            # embeds nothing: it aliases a locally-installed font. This is how
            # next/font's metric-adjustment "… Fallback" families and bare local()
            # faces work. Treat it as a system/local font, not an embedded web font
            # (otherwise it surfaces as a spurious licensing finding).
            if _best_source(rule) is None:
                detected.append(
                    DetectedFont(
                        family=rule.family,
                        embedding=EmbeddingMethod.SYSTEM,
                        font_format=FontFormat.UNKNOWN,
                        source_page=page_url,
                    )
                )
                continue
            applied = rule.family.lower() in used_lower
            font = await _detect_face(fetcher, rule, page_url, page_host, applied, own)
            if font.font_url:
                seen_urls.add(font.font_url)
            detected.append(font)

    for family in used_families:
        if family.lower() in face_families:
            continue
        # Used but never defined by an @font-face: a known system font (no license
        # concern) or an UNKNOWN delivery (referenced but not observed — e.g.
        # injected by JavaScript), which must not read as a clean system font.
        is_system = family.lower() in _KNOWN_SYSTEM_FAMILIES
        detected.append(
            DetectedFont(
                family=family,
                embedding=EmbeddingMethod.SYSTEM if is_system else EmbeddingMethod.UNKNOWN,
                font_format=FontFormat.UNKNOWN,
                source_page=page_url,
            )
        )

    if assets is not None:
        preloads = await _detect_preloads(fetcher, assets, page_url, page_host, own, seen_urls)
        detected.extend(preloads)
        detected.extend(_detect_loaders(assets, page_url))
        # Client-rendered (SPA) fonts leave no static @font-face; recover them from
        # the font URLs shipped inside the page's own JS bundles.
        bundle_fonts = await detect_bundle_fonts(
            fetcher, assets, page_url, page_host, own, seen_urls
        )
        detected.extend(bundle_fonts)

    return detected


async def _detect_preloads(
    fetcher: Fetcher,
    assets: HtmlAssets,
    page_url: str,
    page_host: str,
    own: tuple[str, ...],
    seen_urls: set[str],
) -> list[DetectedFont]:
    """Read <link rel=preload as=font> files not already covered by an @font-face.

    A preloaded font whose @font-face never appears in the static CSS was likely
    wired up by JavaScript; the file itself is still fetchable, so read its name
    table to name it and judge it, instead of missing it.
    """
    preloads = assets.preload_font_urls
    if len(preloads) > _MAX_PRELOADS:
        # Not silent: a page this far over the cap is hostile or broken, and the
        # operator should know coverage was truncated.
        logger.warning(
            "%s: %d font preloads, fetching only the first %d",
            page_url,
            len(preloads),
            _MAX_PRELOADS,
        )
        preloads = preloads[:_MAX_PRELOADS]
    out: list[DetectedFont] = []
    for url in preloads:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        data = await _font_bytes(fetcher, url)
        if data is None:
            continue
        try:
            metadata, file_format = read_font_metadata(data)
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


def _detect_loaders(assets: HtmlAssets, page_url: str) -> list[DetectedFont]:
    """Flag third-party font-loader scripts (Typekit, Font Awesome kit, …).

    We can't enumerate the fonts a loader injects at runtime, but the script's
    presence is a third-party delivery fact worth surfacing (privacy) — one finding
    per provider, so the operator sees the GDPR exposure.
    """
    out: list[DetectedFont] = []
    seen: set[str] = set()
    for src in assets.script_srcs:
        host = (urlsplit(src).hostname or "").lower()
        for marker, label, method in _FONT_LOADERS:
            if host_matches(host, marker) and label not in seen:
                seen.add(label)
                out.append(
                    DetectedFont(
                        family=label,
                        embedding=method,
                        font_format=FontFormat.UNKNOWN,
                        source_page=page_url,
                        font_url=src,
                    )
                )
    return out


async def _detect_face(
    fetcher: Fetcher,
    rule: FontFaceRule,
    page_url: str,
    page_host: str,
    applied: bool,
    own: tuple[str, ...] = (),
) -> DetectedFont:
    source = _best_source(rule)
    font_url = source.url if source else None
    fmt = source.font_format if source else FontFormat.UNKNOWN
    embedding = classify_embedding(font_url, page_host, own)

    metadata = None
    if font_url:
        data = await _font_bytes(fetcher, font_url)
        if data:
            try:
                metadata, file_format = read_font_metadata(data)
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
