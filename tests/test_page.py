"""Per-page detection: source ranking, system fonts, applied flag, robustness."""

from __future__ import annotations

import base64

import pytest

from fontsentry.crawl.fetcher import FetchResult
from fontsentry.detect.css import FontFaceRule, FontSource
from fontsentry.detect.page import _best_source, detect_page
from fontsentry.models import EmbeddingMethod, FontFormat
from tests.factories import build_test_font

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


async def test_detect_page_data_uri_reads_metadata() -> None:
    # A base64 data: URI embeds the font inline — decode it and read its name table
    # (fsType, family) instead of trying to fetch a non-URL.
    font_bytes = build_test_font(family_name="Inline Face", fs_type=0x0002)
    b64 = base64.b64encode(font_bytes).decode()
    css = (
        f'@font-face{{font-family:"Inline Face";src:url(data:font/ttf;base64,{b64})}}'
        '.a{font-family:"Inline Face"}'
    )
    stub = _StubFetcher({PAGE: _page(f"<style>{css}</style>")})
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    face = dets["Inline Face"]
    assert face.embedding is EmbeddingMethod.SELF_HOSTED
    assert face.metadata is not None
    assert face.metadata.fs_type == 0x0002


async def test_detect_page_preload_without_fontface() -> None:
    # A preloaded font with no static @font-face (wired up by JS) is still fetchable
    # — read the file to name and judge it rather than miss it.
    font_bytes = build_test_font(family_name="Preloaded Sans")
    stub = _StubFetcher(
        {
            PAGE: _page('<link rel="preload" as="font" href="/p.woff2" type="font/woff2">'),
            "https://example.com/p.woff2": _result("x", font_bytes, "font/woff2"),
        }
    )
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Preloaded Sans" in dets
    assert dets["Preloaded Sans"].embedding is EmbeddingMethod.SELF_HOSTED


async def test_import_cycle_terminates() -> None:
    # a.css imports b.css imports a.css: the BFS seen-set must terminate the walk
    # and both sheets' fonts must still be collected exactly once.
    a = "https://example.com/a.css"
    b = "https://example.com/b.css"
    stub = _StubFetcher(
        {
            PAGE: _page('<link rel="stylesheet" href="/a.css">'),
            a: _result(a, b'@import url("/b.css"); .x{font-family:CycleA}', "text/css"),
            b: _result(b, b'@import url("/a.css"); .y{font-family:CycleB}', "text/css"),
        }
    )
    dets = {d.family for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert {"CycleA", "CycleB"} <= dets  # both reached, and the call returned


async def test_stylesheet_cap_truncation_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # "Silent failures are forbidden": coverage truncated by the stylesheet cap
    # must be visible to the operator, not swallowed.
    from fontsentry.detect.page import _MAX_STYLESHEETS

    links = "".join(
        f'<link rel="stylesheet" href="/s{i}.css">' for i in range(_MAX_STYLESHEETS + 5)
    )
    routes: dict[str, FetchResult | None] = {PAGE: _page(links)}
    for i in range(_MAX_STYLESHEETS + 5):
        url = f"https://example.com/s{i}.css"
        routes[url] = _result(url, b".x{color:red}", "text/css")
    with caplog.at_level("WARNING"):
        await detect_page(_StubFetcher(routes), PAGE)  # type: ignore[arg-type]
    assert any("stylesheet cap" in r.message for r in caplog.records)


async def test_preload_fanout_is_capped() -> None:
    # Regression: preloads were the one fetch path without a per-page bound — a
    # hostile page with thousands of <link rel=preload as=font> drove a fetch each.
    from fontsentry.detect.page import _MAX_PRELOADS

    class _CountingFetcher(_StubFetcher):
        def __init__(self, routes: dict[str, FetchResult | None]) -> None:
            super().__init__(routes)
            self.fetched: list[str] = []

        async def fetch(self, url: str) -> FetchResult | None:
            self.fetched.append(url)
            return await super().fetch(url)

    links = "".join(
        f'<link rel="preload" as="font" href="/f{i}.woff2">' for i in range(_MAX_PRELOADS + 25)
    )
    stub = _CountingFetcher({PAGE: _page(links)})
    await detect_page(stub, PAGE)  # type: ignore[arg-type]
    font_fetches = [u for u in stub.fetched if u.endswith(".woff2")]
    assert len(font_fetches) == _MAX_PRELOADS


async def test_detect_page_flags_font_loader_script() -> None:
    # A third-party loader script (Adobe Typekit) delivers fonts at runtime; flag
    # the provider as a third-party finding even though we can't enumerate the fonts.
    stub = _StubFetcher({PAGE: _page('<script src="https://use.typekit.net/abc.js"></script>')})
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    loader = next(v for k, v in dets.items() if "Adobe" in k)
    assert loader.embedding is EmbeddingMethod.ADOBE_FONTS


async def test_loader_lookalike_host_not_flagged() -> None:
    # Regression: substring matching flagged use.typekit.net.evil.example as an
    # Adobe Fonts finding; only the exact host or a dot-bounded subdomain counts.
    stub = _StubFetcher(
        {PAGE: _page('<script src="https://use.typekit.net.evil.example/abc.js"></script>')}
    )
    dets = await detect_page(stub, PAGE)  # type: ignore[arg-type]
    assert not any("Adobe" in d.family for d in dets)


async def test_detect_page_own_hosts_are_first_party() -> None:
    # A font on a separate domain the operator declares as their own is self-hosted,
    # not a third-party privacy leak.
    home = "https://mybrand.com/"
    css = '@font-face{font-family:"Brand";src:url(https://assets.mybrand.net/b.woff2)}.a{font-family:Brand}'
    html = f"<style>{css}</style>".encode()
    stub = _StubFetcher(
        {
            home: _result(home, html, "text/html"),
            "https://assets.mybrand.net/b.woff2": _result("x", b"garbage", "font/woff2"),
        }
    )
    fonts = await detect_page(stub, home, own_hosts=["assets.mybrand.net"])  # type: ignore[arg-type]
    dets = {d.family: d for d in fonts}
    assert dets["Brand"].embedding is EmbeddingMethod.SELF_HOSTED


async def test_detect_page_local_only_face_is_system() -> None:
    # A @font-face whose only source is local() (e.g. next/font metric-adjustment
    # "… Fallback" families) embeds nothing — a local alias, not a licensable font.
    css = (
        '@font-face{font-family:"Adjusted Fallback";src:local("Arial")}'
        ".a{font-family:'Adjusted Fallback'}"
    )
    stub = _StubFetcher({PAGE: _page(f"<style>{css}</style>")})
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert dets["Adjusted Fallback"].embedding is EmbeddingMethod.SYSTEM


async def test_detect_page_unknown_delivery_for_unobserved_family() -> None:
    # A non-system family used in font-family with no @font-face (e.g. injected by
    # JavaScript) is UNKNOWN delivery — not a clean system font.
    stub = _StubFetcher({PAGE: _page("<style>.x{font-family:'Injected Sans',sans-serif}</style>")})
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
