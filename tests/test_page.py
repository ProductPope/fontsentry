"""Per-page detection: source ranking, system fonts, applied flag, robustness."""

from __future__ import annotations

from fontsentry.crawl.fetcher import FetchResult
from fontsentry.detect.css import FontFaceRule, FontSource
from fontsentry.detect.page import _best_source, detect_page
from fontsentry.models import EmbeddingMethod, FontFormat

PAGE = "https://example.com/"


class _StubFetcher:
    """Duck-typed Fetcher: returns a preset FetchResult per URL (or None)."""

    def __init__(self, routes: dict[str, FetchResult | None]) -> None:
        self._routes = routes

    async def fetch(self, url: str) -> FetchResult | None:
        return self._routes.get(url)


def _result(url: str, content: bytes, content_type: str) -> FetchResult:
    return FetchResult(url=url, status=200, content=content, content_type=content_type)


def _page(html: str) -> FetchResult:
    return _result(PAGE, html.encode(), "text/html")


def test_best_source_prefers_woff2() -> None:
    rule = FontFaceRule(
        family="X",
        sources=[
            FontSource(url="a.ttf", font_format=FontFormat.TTF),
            FontSource(url="b.woff2", font_format=FontFormat.WOFF2),
        ],
    )
    best = _best_source(rule)
    assert best is not None and best.font_format is FontFormat.WOFF2


def test_best_source_none_when_no_sources() -> None:
    assert _best_source(FontFaceRule(family="X")) is None


async def test_detect_page_system_font() -> None:
    stub = _StubFetcher({PAGE: _page("<style>body{font-family:Georgia,serif}</style>")})
    dets = await detect_page(stub, PAGE)  # type: ignore[arg-type]
    assert len(dets) == 1
    assert dets[0].family == "Georgia"
    assert dets[0].embedding is EmbeddingMethod.SYSTEM


async def test_detect_page_unknown_delivery_for_unobserved_family() -> None:
    # A non-system family used in font-family with no @font-face (e.g. injected by
    # JavaScript) is UNKNOWN delivery — not a clean system font.
    stub = _StubFetcher(
        {PAGE: _page("<style>.x{font-family:'Injected Sans',sans-serif}</style>")}
    )
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert dets["Injected Sans"].embedding is EmbeddingMethod.UNKNOWN


async def test_detect_page_follows_at_import() -> None:
    # A font delivered via an @imported sheet must be detected (not seen only as a
    # usage and misclassified as a system font).
    page_html = '<style>@import url("/fonts.css");.a{font-family:Imported}</style>'
    fonts_css = '@font-face{font-family:"Imported";src:url(/i.woff2)}'
    stub = _StubFetcher(
        {
            PAGE: _page(page_html),
            "https://example.com/fonts.css": _result("x", fonts_css.encode(), "text/css"),
            "https://example.com/i.woff2": _result("x", b"garbage", "font/woff2"),
        }
    )
    by = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Imported" in by
    assert by["Imported"].embedding is EmbeddingMethod.SELF_HOSTED


async def test_detect_page_applied_flag_and_read_error() -> None:
    css = (
        '@font-face{font-family:"Demo";src:url(/d.woff2)}'
        '@font-face{font-family:"Ghost";src:url(/g.woff2)}'
        ".a{font-family:Demo}"
    )
    stub = _StubFetcher(
        {
            PAGE: _page(f"<style>{css}</style>"),
            "https://example.com/d.woff2": _result("x", b"garbage", "font/woff2"),
            "https://example.com/g.woff2": _result("x", b"garbage", "font/woff2"),
        }
    )
    by = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert by["Demo"].applied is True  # referenced by .a { font-family: Demo }
    assert by["Ghost"].applied is False  # defined but never used
    assert by["Demo"].metadata is None  # garbage bytes -> FontReadError swallowed


async def test_detect_page_decodes_non_utf8_charset() -> None:
    # A latin-1 page with a non-ASCII @font-face family must decode correctly
    # (Content-Type charset honoured), not turn into mojibake that breaks matching.
    css = '@font-face{font-family:"Ténör Sans";src:url(/f.woff2)}.a{font-family:"Ténör Sans"}'
    html = f"<style>{css}</style>"
    stub = _StubFetcher(
        {
            PAGE: _result(PAGE, html.encode("latin-1"), "text/html; charset=latin-1"),
            "https://example.com/f.woff2": _result("x", b"garbage", "font/woff2"),
        }
    )
    families = {d.family for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Ténör Sans" in families


async def test_detect_page_non_html_returns_empty() -> None:
    stub = _StubFetcher({PAGE: _result(PAGE, b"{}", "application/json")})
    assert await detect_page(stub, PAGE) == []  # type: ignore[arg-type]


async def test_detect_page_unreachable_returns_empty() -> None:
    assert await detect_page(_StubFetcher({}), PAGE) == []  # type: ignore[arg-type]
