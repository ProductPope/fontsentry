"""HTML parsing: collect stylesheets, inline CSS, font references and usages.

selectolax gives a fast, lenient DOM. We only pull out what the detection
pipeline needs; resolving and fetching linked stylesheets is the crawl layer's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from fontsentry.detect.css import parse_font_families


@dataclass
class HtmlAssets:
    stylesheet_links: list[str] = field(default_factory=list)
    inline_styles: list[str] = field(default_factory=list)
    preload_font_urls: list[str] = field(default_factory=list)
    script_srcs: list[str] = field(default_factory=list)
    font_families: set[str] = field(default_factory=set)


def _resolve(href: str, base_url: str | None) -> str:
    return urljoin(base_url, href) if base_url else href


def parse_html(html: str, base_url: str | None = None) -> HtmlAssets:
    """Extract stylesheet links, inline <style> CSS, preloaded fonts, and usages."""

    tree = HTMLParser(html)
    assets = HtmlAssets()

    for link in tree.css("link"):
        attrs = link.attributes
        rel = (attrs.get("rel") or "").lower()
        href = attrs.get("href")
        if not href:
            continue
        if "stylesheet" in rel:
            assets.stylesheet_links.append(_resolve(href, base_url))
        elif "preload" in rel and (attrs.get("as") or "").lower() == "font":
            assets.preload_font_urls.append(_resolve(href, base_url))

    for script in tree.css("script"):
        src = script.attributes.get("src")
        if src:
            assets.script_srcs.append(_resolve(src, base_url))

    for style in tree.css("style"):
        css_text = style.text(deep=True)
        if css_text:
            assets.inline_styles.append(css_text)
            assets.font_families.update(parse_font_families(css_text))

    for node in tree.css("[style]"):
        inline = node.attributes.get("style")
        if inline:
            # Wrap the declaration block so the CSS parser can read it.
            assets.font_families.update(parse_font_families(f"*{{{inline}}}"))

    return assets
