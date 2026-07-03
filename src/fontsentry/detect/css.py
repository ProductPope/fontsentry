"""CSS parsing: extract @font-face rules and referenced font-family names.

Uses tinycss2 so we read the cascade structurally instead of with regexes.
Network fetching of linked stylesheets happens in the crawl layer; everything
here operates on CSS text already in hand, which keeps it pure and testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

import tinycss2

from fontsentry.models import FontFormat

# format() hint string -> FontFormat
_FORMAT_HINTS: dict[str, FontFormat] = {
    "woff2": FontFormat.WOFF2,
    "woff": FontFormat.WOFF,
    "truetype": FontFormat.TTF,
    "opentype": FontFormat.OTF,
    "embedded-opentype": FontFormat.EOT,
}

# file extension -> FontFormat
_FORMAT_EXTENSIONS: dict[str, FontFormat] = {
    ".woff2": FontFormat.WOFF2,
    ".woff": FontFormat.WOFF,
    ".ttf": FontFormat.TTF,
    ".otf": FontFormat.OTF,
    ".eot": FontFormat.EOT,
}


@dataclass(frozen=True)
class FontSource:
    url: str
    font_format: FontFormat


@dataclass
class FontFaceRule:
    family: str
    sources: list[FontSource] = field(default_factory=list)


def format_from_hint(hint: str) -> FontFormat:
    return _FORMAT_HINTS.get(hint.strip().strip("'\"").lower(), FontFormat.UNKNOWN)


def format_from_url(url: str) -> FontFormat:
    path = urlparse(url).path
    suffix = PurePosixPath(path).suffix.lower()
    return _FORMAT_EXTENSIONS.get(suffix, FontFormat.UNKNOWN)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
        return value[1:-1]
    return value


# A CSS escape: a backslash followed by 1-6 hex digits (+ optional trailing
# whitespace) for a codepoint, or a backslash followed by any other character
# for that character literally. Unquoted family names use `\ ` for spaces, so
# `Font Awesome\ 5 Free` must normalize to the same name as the quoted form.
_CSS_ESCAPE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})[ \t\n]?|(.))", re.DOTALL)


def _unescape_css(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        hex_digits, literal = match.group(1), match.group(2)
        if hex_digits is not None:
            code = int(hex_digits, 16)
            return chr(code) if 0 < code <= 0x10FFFF else "�"
        return literal

    return _CSS_ESCAPE.sub(repl, value)


def _family_name(raw: str) -> str:
    """Normalize a serialized font-family token into a comparable name:
    strip quotes, then unescape CSS backslash escapes (e.g. escaped spaces)."""
    return _unescape_css(_unquote(raw)).strip()


def _declarations(content: list[Any]) -> list[Any]:
    # tinycss2 returns Declaration and ParseError nodes; keep only declarations.
    parsed = tinycss2.parse_declaration_list(content, skip_whitespace=True, skip_comments=True)
    return [d for d in parsed if getattr(d, "type", None) == "declaration"]


def _serialize(tokens: list[Any]) -> str:
    return str(tinycss2.serialize(tokens)).strip()


def _parse_src(tokens: list[Any], base_url: str | None) -> list[FontSource]:
    """Walk the tokens of a `src:` declaration into (url, format) pairs."""

    sources: list[FontSource] = []
    pending_url: str | None = None
    pending_format = FontFormat.UNKNOWN

    def flush() -> None:
        nonlocal pending_url, pending_format
        if pending_url is not None:
            url = urljoin(base_url, pending_url) if base_url else pending_url
            fmt = pending_format
            if fmt is FontFormat.UNKNOWN:
                fmt = format_from_url(url)
            sources.append(FontSource(url=url, font_format=fmt))
        pending_url = None
        pending_format = FontFormat.UNKNOWN

    for token in tokens:
        ttype = getattr(token, "type", None)
        if ttype == "url":
            flush()
            pending_url = token.value
        elif ttype == "function":
            name = token.lower_name
            if name == "url":
                flush()
                pending_url = _first_string(token.arguments)
            elif name == "format" and pending_url is not None:
                hint = _first_string(token.arguments)
                if hint:
                    pending_format = format_from_hint(hint)
        elif ttype == "literal" and token.value == ",":
            flush()

    flush()
    return sources


def _first_string(arguments: list[Any]) -> str:
    for arg in arguments:
        if getattr(arg, "type", None) == "string":
            return str(arg.value)
    return ""


def parse_font_faces(css_text: str, base_url: str | None = None) -> list[FontFaceRule]:
    """Extract every @font-face rule with its family name and resolved sources."""

    rules: list[FontFaceRule] = []
    for node in tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True):
        if getattr(node, "type", None) != "at-rule" or node.lower_at_keyword != "font-face":
            continue
        if node.content is None:
            continue

        family = ""
        sources: list[FontSource] = []
        for decl in _declarations(node.content):
            name = decl.lower_name
            if name == "font-family":
                family = _family_name(_serialize(decl.value))
            elif name == "src":
                sources = _parse_src(decl.value, base_url)

        if family:
            rules.append(FontFaceRule(family=family, sources=sources))
    return rules


def parse_font_families(css_text: str) -> set[str]:
    """Collect family names referenced by `font-family` / `font` in style rules.

    These are *usages* (which fonts a page asks for), used later to spot system
    fonts: families requested but never defined by an @font-face.
    """

    families: set[str] = set()
    for node in tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True):
        if getattr(node, "type", None) != "qualified-rule":
            continue
        for decl in _declarations(node.content):
            if decl.lower_name in ("font-family", "font"):
                families.update(_split_families(_serialize(decl.value)))
    return families


def _split_families(value: str) -> set[str]:
    out: set[str] = set()
    for part in value.split(","):
        name = _family_name(part)
        # Drop shorthand noise (sizes, weights), generic keywords, and CSS
        # custom-property references (e.g. `var(--bs-body-font-family)`), which
        # are variable lookups, not real family names.
        if (
            name
            and not name[0].isdigit()
            and not name.lower().startswith("var(")
            and name.lower() not in _GENERIC_FAMILIES
        ):
            out.add(name)
    return out


_GENERIC_FAMILIES = {
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-serif",
    "ui-sans-serif",
    "ui-monospace",
    "inherit",
    "initial",
    "unset",
    "normal",
    "bold",
}
