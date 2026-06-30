"""Generate the demo font binaries with crafted name tables.

Run with `uv run python demo/_generate_assets.py`. Reproducible and offline: it
builds tiny but valid TTF/WOFF2 files so the committed demo dataset matches the
registry and rules. Re-run after changing any font's metadata below.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

DEMO = Path(__file__).resolve().parent
SITES = DEMO / "sites"


def build_font(
    *,
    family: str,
    foundry: str,
    copyright_text: str | None,
    license_text: str | None,
    glyph_count: int,
    flavor: str | None = None,
) -> bytes:
    glyph_order = [".notdef", "space", "A"] + [f"g{i}" for i in range(glyph_count)]
    fb = FontBuilder(unitsPerEm=1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x20: "space", 0x41: "A"})

    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf(dict.fromkeys(glyph_order, empty))
    fb.setupHorizontalMetrics(dict.fromkeys(glyph_order, (500, 0)))
    fb.setupHorizontalHeader(ascent=800, descent=-200)

    names = {
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{foundry}: {family}: 2026",
        "manufacturer": foundry,
        "designer": "Demo Designer",
    }
    if copyright_text is not None:
        names["copyright"] = copyright_text
    if license_text is not None:
        names["licenseDescription"] = license_text
    fb.setupNameTable(names)
    fb.setupOS2()
    fb.setupPost()

    if flavor is not None:
        fb.font.flavor = flavor

    buffer = BytesIO()
    fb.save(buffer)
    return buffer.getvalue()


def main() -> None:
    fonts = {
        "example-demo.test/fonts/atlas.ttf": build_font(
            family="Atlas Grotesk Private",
            foundry="Meridian Letterworks",
            copyright_text="Copyright 2026 Meridian Letterworks. Desktop use only.",
            license_text="Desktop license. Web embedding and self-hosting not permitted.",
            glyph_count=300,
        ),
        "example-demo.test/fonts/harbor.woff2": build_font(
            family="Harbor Serif",
            foundry="Northwind Type",
            copyright_text="Copyright 2026 Northwind Type.",
            license_text="Web font license, up to 3 domains.",
            glyph_count=300,
            flavor="woff2",
        ),
        "example-demo.test/fonts/acme.ttf": build_font(
            family="Acme Display",
            foundry="Acme Type",
            copyright_text=None,  # stripped: triggers missing-copyright
            license_text=None,
            glyph_count=300,
        ),
        "example-demo.test/fonts/publicglyphs.woff2": build_font(
            family="Public Glyphs Sans",
            foundry="Public Glyphs Foundation",
            copyright_text="Copyright 2026 Public Glyphs Foundation.",
            license_text="SIL Open Font License (OFL) v1.1.",
            glyph_count=50,  # small: triggers low-confidence subset signal
            flavor="woff2",
        ),
        "blog.example-demo.test/fonts/acme.ttf": build_font(
            family="Acme Display",
            foundry="Acme Type",
            copyright_text=None,  # same unregistered font, reused on a subdomain
            license_text=None,
            glyph_count=300,
        ),
        "example-shop.test/fonts/atlas.ttf": build_font(
            family="Atlas Grotesk Private",
            foundry="Meridian Letterworks",
            copyright_text="Copyright 2026 Meridian Letterworks. Desktop use only.",
            license_text="Desktop license. Web embedding and self-hosting not permitted.",
            glyph_count=300,
        ),
        "example-shop.test/fonts/expired.woff2": build_font(
            family="Expired Face",
            foundry="Old Foundry",
            copyright_text="Copyright 2024 Old Foundry.",
            license_text="Web font license (annual).",
            glyph_count=300,
            flavor="woff2",
        ),
    }

    for rel, data in fonts.items():
        path = SITES / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {rel} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
