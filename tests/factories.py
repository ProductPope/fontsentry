"""Build tiny, valid font files in memory for tests — no committed binaries.

Reproducible and offline: each call assembles a minimal TTF (optionally WOFF-
flavored) with a crafted name table, so font-reading tests stay deterministic.
"""

from __future__ import annotations

from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

# FontBuilder name-table keys -> the OpenType name IDs they map to.
_NAME_KEYS = (
    "copyright",
    "familyName",
    "styleName",
    "uniqueFontIdentifier",
    "manufacturer",
    "designer",
    "licenseDescription",
    "licenseInfoURL",
)


def build_test_font(
    *,
    family_name: str = "Demo Sans",
    style_name: str = "Regular",
    copyright: str | None = "Copyright 2026 Demo Owner",
    manufacturer: str | None = "Demo Owner",
    designer: str | None = "A. Designer",
    license_description: str | None = "Demo web license.",
    license_url: str | None = "https://example.invalid/license",
    unique_id: str | None = "DemoOwner: Demo Sans: 2026",
    extra_glyphs: int = 0,
    flavor: str | None = None,
    fs_type: int = 0,
) -> bytes:
    """Return font bytes with the given name-table fields. ``flavor`` may be 'woff'."""

    glyph_order = [".notdef", "space", "A"]
    glyph_order += [f"g{i}" for i in range(extra_glyphs)]

    fb = FontBuilder(unitsPerEm=1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x20: "space", 0x41: "A"})

    pen = TTGlyphPen(None)
    empty = pen.glyph()
    fb.setupGlyf(dict.fromkeys(glyph_order, empty))
    fb.setupHorizontalMetrics(dict.fromkeys(glyph_order, (500, 0)))
    fb.setupHorizontalHeader(ascent=800, descent=-200)

    name_fields = {
        "familyName": family_name,
        "styleName": style_name,
        "copyright": copyright,
        "manufacturer": manufacturer,
        "designer": designer,
        "licenseDescription": license_description,
        "licenseInfoURL": license_url,
        "uniqueFontIdentifier": unique_id,
    }
    fb.setupNameTable({k: v for k, v in name_fields.items() if v is not None})
    fb.setupOS2(fsType=fs_type)
    fb.setupPost()

    if flavor is not None:
        fb.font.flavor = flavor

    buffer = BytesIO()
    fb.save(buffer)
    return buffer.getvalue()
