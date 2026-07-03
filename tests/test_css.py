"""CSS parsing: @font-face extraction, format hints, family usages."""

from __future__ import annotations

from fontsentry.detect import css
from fontsentry.models import FontFormat


def test_font_face_with_format_hints() -> None:
    text = """
    @font-face {
        font-family: 'Atlas Grotesk Private';
        src: url('/fonts/atlas.woff2') format('woff2'),
             url('/fonts/atlas.woff') format('woff');
        font-weight: 400;
    }
    """
    rules = css.parse_font_faces(text, base_url="https://example.com/style.css")
    assert len(rules) == 1
    rule = rules[0]
    assert rule.family == "Atlas Grotesk Private"
    assert rule.sources[0].url == "https://example.com/fonts/atlas.woff2"
    assert rule.sources[0].font_format is FontFormat.WOFF2
    assert rule.sources[1].font_format is FontFormat.WOFF


def test_font_face_format_inferred_from_extension() -> None:
    text = "@font-face { font-family: Harbor; src: url('harbor.ttf'); }"
    rules = css.parse_font_faces(text)
    assert rules[0].sources[0].font_format is FontFormat.TTF


def test_bare_url_token_supported() -> None:
    text = "@font-face { font-family: Harbor; src: url(harbor.otf) format('opentype'); }"
    rules = css.parse_font_faces(text)
    assert rules[0].sources[0].url == "harbor.otf"
    assert rules[0].sources[0].font_format is FontFormat.OTF


def test_multiple_font_faces() -> None:
    text = (
        "@font-face { font-family: A; src: url(a.woff2); }"
        "@font-face { font-family: B; src: url(b.woff); }"
    )
    families = {r.family for r in css.parse_font_faces(text)}
    assert families == {"A", "B"}


def test_non_font_face_rules_ignored() -> None:
    text = "body { color: red; } @media screen { p { font-family: X; } }"
    assert css.parse_font_faces(text) == []


def test_parse_font_families_usage() -> None:
    text = "h1 { font-family: 'Harbor Serif', Ledger, serif; } p { font-family: Demo Sans; }"
    families = css.parse_font_families(text)
    assert "Harbor Serif" in families
    assert "Demo Sans" in families
    assert "serif" not in families  # generic keyword dropped


def test_parse_font_families_drops_var_references() -> None:
    text = "body { font-family: var(--bs-body-font-family), 'Demo Sans', sans-serif; }"
    families = css.parse_font_families(text)
    assert "Demo Sans" in families
    assert not any(f.lower().startswith("var(") for f in families)


def test_escaped_spaces_in_family_are_unescaped() -> None:
    # An unquoted family with backslash-escaped spaces must normalize to the same
    # name as its quoted form — otherwise the same font shows up twice.
    text = (
        ".a { font-family: Font Awesome\\ 5 Free, sans-serif; }"
        " .b { font-family: 'Font Awesome 5 Free'; }"
    )
    families = css.parse_font_families(text)
    assert "Font Awesome 5 Free" in families
    assert not any("\\" in f for f in families)


def test_font_face_family_unescaped() -> None:
    text = "@font-face { font-family: Font Awesome\\ 5 Free; src: url(fa.woff2); }"
    assert css.parse_font_faces(text)[0].family == "Font Awesome 5 Free"


def test_format_helpers() -> None:
    assert css.format_from_hint("woff2") is FontFormat.WOFF2
    assert css.format_from_hint("'truetype'") is FontFormat.TTF
    assert css.format_from_hint("bogus") is FontFormat.UNKNOWN
    assert css.format_from_url("https://x/y/font.eot?v=2") is FontFormat.EOT
    assert css.format_from_url("https://x/y/font") is FontFormat.UNKNOWN
