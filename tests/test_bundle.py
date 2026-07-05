"""Static bundle scan: recover SPA fonts from JS bundles, safely and offline."""

from __future__ import annotations

from fontsentry.crawl.fetcher import FetchResult
from fontsentry.detect.page import detect_page
from fontsentry.models import EmbeddingMethod
from tests.factories import build_test_font
from tests.test_page import PAGE, _page, _result, _StubFetcher

BUNDLE_URL = "https://example.com/main.js"
FONT_URL = "https://example.com/assets/fonts/brand.woff2"


def _js(body: str) -> FetchResult:
    return _result(BUNDLE_URL, body.encode(), "application/javascript")


async def test_bundle_font_recovered_from_js() -> None:
    # A SPA leaves no static @font-face; the font URL lives inside the JS bundle.
    font = build_test_font(family_name="Bundle Sans", flavor="woff2")
    stub = _StubFetcher(
        {
            PAGE: _page('<head><script src="/main.js"></script></head>'),
            BUNDLE_URL: _js('var f=e("/assets/fonts/brand.woff2");'),
            FONT_URL: _result(FONT_URL, font, "font/woff2"),
        }
    )
    dets = {d.family: d for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Bundle Sans" in dets
    assert dets["Bundle Sans"].embedding is EmbeddingMethod.SELF_HOSTED
    assert dets["Bundle Sans"].metadata is not None


async def test_bundle_cross_site_script_not_fetched() -> None:
    # Third-party scripts (analytics, etc.) are never scanned.
    font = build_test_font(family_name="Offsite Sans", flavor="woff2")
    stub = _StubFetcher(
        {
            PAGE: _page('<script src="https://cdn.other.com/app.js"></script>'),
            "https://cdn.other.com/app.js": _result(
                "https://cdn.other.com/app.js", b'x="/assets/fonts/x.woff2"', "text/javascript"
            ),
            "https://example.com/assets/fonts/x.woff2": _result(FONT_URL, font, "font/woff2"),
        }
    )
    families = {d.family for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Offsite Sans" not in families


async def test_bundle_unreadable_url_skipped() -> None:
    # A .woff2 string that isn't actually a font is fetched but discarded.
    stub = _StubFetcher(
        {
            PAGE: _page('<script src="/main.js"></script>'),
            BUNDLE_URL: _js('load("/assets/fonts/broken.woff2")'),
            "https://example.com/assets/fonts/broken.woff2": _result(
                FONT_URL, b"not a font", "font/woff2"
            ),
        }
    )
    assert await detect_page(stub, PAGE) == []  # type: ignore[arg-type]
