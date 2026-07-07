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


async def test_bundle_relative_url_resolves_against_bundle_host() -> None:
    # Regression: a root-relative font path inside a bundle served from a declared
    # asset domain belongs to that domain — resolving it against the page host
    # produced a 404 and the font vanished (the ADR 0004 asset-CDN case).
    asset_js = "https://static.brand-assets.test/main.js"
    asset_font = "https://static.brand-assets.test/fonts/brand.woff2"
    font = build_test_font(family_name="Asset Sans", flavor="woff2")
    stub = _StubFetcher(
        {
            PAGE: _page(f'<script src="{asset_js}"></script>'),
            asset_js: _result(asset_js, b'var f=e("/fonts/brand.woff2");', "text/javascript"),
            asset_font: _result(asset_font, font, "font/woff2"),
        }
    )
    dets = {
        d.family: d
        for d in await detect_page(
            stub,  # type: ignore[arg-type]
            PAGE,
            own_hosts=("static.brand-assets.test",),
        )
    }
    assert "Asset Sans" in dets
    assert dets["Asset Sans"].font_url == asset_font


async def test_bundle_json_escaped_url_recovered() -> None:
    # Regression: webpack/Vite manifests embed URLs JSON-escaped (https:\/\/…);
    # the extraction regex needs the unescaped form or these bundles yield nothing.
    font = build_test_font(family_name="Manifest Sans", flavor="woff2")
    escaped = r'{"font":"https:\/\/example.com\/assets\/fonts\/brand.woff2"}'
    stub = _StubFetcher(
        {
            PAGE: _page('<script src="/main.js"></script>'),
            BUNDLE_URL: _js(escaped),
            FONT_URL: _result(FONT_URL, font, "font/woff2"),
        }
    )
    families = {d.family for d in await detect_page(stub, PAGE)}  # type: ignore[arg-type]
    assert "Manifest Sans" in families


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


async def test_bundle_same_site_works_on_non_default_port() -> None:
    # Regression: page_host kept ":port", the dot-bounded same-site check failed,
    # and every same-origin bundle on a non-443 port was silently skipped.
    page = "https://staging.example.com:8443/"
    bundle = "https://staging.example.com:8443/main.js"
    font_url = "https://staging.example.com:8443/fonts/port.woff2"
    font = build_test_font(family_name="Port Sans", flavor="woff2")
    stub = _StubFetcher(
        {
            page: _result(page, b'<script src="/main.js"></script>', "text/html"),
            bundle: _result(bundle, b'e("/fonts/port.woff2")', "text/javascript"),
            font_url: _result(font_url, font, "font/woff2"),
        }
    )
    dets = {d.family: d for d in await detect_page(stub, page)}  # type: ignore[arg-type]
    assert "Port Sans" in dets
    assert dets["Port Sans"].embedding is EmbeddingMethod.SELF_HOSTED


async def test_bundle_cache_dedupes_fetches_but_keeps_attribution() -> None:
    # Two pages referencing the same bundle: the bundle and the font are fetched
    # once (crawl-level cache), yet BOTH pages report the font — attribution
    # (domains, page counts, cross-domain verdicts) must not change.
    from fontsentry.detect.bundle import BundleCache

    page2 = "https://example.com/about"
    font = build_test_font(family_name="Cached Sans", flavor="woff2")

    class _CountingFetcher(_StubFetcher):
        def __init__(self, routes: dict[str, FetchResult | None]) -> None:
            super().__init__(routes)
            self.fetched: list[str] = []

        async def fetch(self, url: str) -> FetchResult | None:
            self.fetched.append(url)
            return await super().fetch(url)

    stub = _CountingFetcher(
        {
            PAGE: _page('<script src="/main.js"></script>'),
            page2: _result(page2, b'<script src="/main.js"></script>', "text/html"),
            BUNDLE_URL: _js('var f=e("/assets/fonts/brand.woff2");'),
            FONT_URL: _result(FONT_URL, font, "font/woff2"),
        }
    )
    cache = BundleCache()
    first = await detect_page(stub, PAGE, bundle_cache=cache)  # type: ignore[arg-type]
    second = await detect_page(stub, page2, bundle_cache=cache)  # type: ignore[arg-type]

    assert any(d.family == "Cached Sans" for d in first)
    assert any(d.family == "Cached Sans" for d in second)  # attribution kept
    assert stub.fetched.count(BUNDLE_URL) == 1  # network deduped
    assert stub.fetched.count(FONT_URL) == 1
