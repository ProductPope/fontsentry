"""HTML asset extraction: stylesheet links, inline CSS, preloads, usages."""

from __future__ import annotations

from fontsentry.detect.html import parse_html

_PAGE = """
<!doctype html>
<html><head>
  <link rel="stylesheet" href="/css/site.css">
  <link rel="preload" as="font" href="/fonts/atlas.woff2" type="font/woff2" crossorigin>
  <link rel="icon" href="/favicon.ico">
  <style>
    @font-face { font-family: Harbor; src: url(/fonts/harbor.woff2); }
    h1 { font-family: Harbor, serif; }
  </style>
</head>
<body>
  <p style="font-family: 'Inline Face', sans-serif;">hi</p>
</body></html>
"""


def test_parse_html_collects_assets() -> None:
    assets = parse_html(_PAGE, base_url="https://example.com/")

    assert "https://example.com/css/site.css" in assets.stylesheet_links
    assert "https://example.com/fonts/atlas.woff2" in assets.preload_font_urls
    # icon link is neither stylesheet nor font preload
    assert all("favicon" not in link for link in assets.stylesheet_links)

    assert "Harbor" in assets.font_families
    assert "Inline Face" in assets.font_families
    assert "serif" not in assets.font_families


def test_inline_styles_captured() -> None:
    assets = parse_html(_PAGE)
    joined = "\n".join(assets.inline_styles)
    assert "@font-face" in joined
    assert "Harbor" in joined
