"""Font-file metadata reading via fonttools, using in-memory crafted fonts."""

from __future__ import annotations

import pytest

from fontsentry.detect.fontfile import FontReadError, read_font_metadata
from fontsentry.models import FontFormat
from tests.factories import build_test_font


def test_reads_name_table_fields() -> None:
    data = build_test_font(
        family_name="Atlas Grotesk Private",
        manufacturer="Meridian Letterworks",
        designer="J. Meridian",
        copyright="Copyright 2026 Meridian",
        license_description="Desktop license. No web embedding.",
        license_url="https://example.invalid/eula",
        unique_id="Meridian: Atlas Grotesk Private",
    )
    meta, fmt = read_font_metadata(data)

    assert fmt is FontFormat.TTF
    assert meta.family_name == "Atlas Grotesk Private"
    assert meta.owner == "Meridian Letterworks"
    assert meta.designer == "J. Meridian"
    assert meta.copyright == "Copyright 2026 Meridian"
    assert meta.license_description == "Desktop license. No web embedding."
    assert meta.license_url == "https://example.invalid/eula"
    assert meta.num_glyphs == 3


def test_reads_os2_fstype() -> None:
    installable, _ = read_font_metadata(build_test_font(fs_type=0))
    assert installable.fs_type == 0
    restricted, _ = read_font_metadata(build_test_font(fs_type=0x0002))
    assert restricted.fs_type == 0x0002


def test_woff_flavor_detected() -> None:
    data = build_test_font(flavor="woff")
    _meta, fmt = read_font_metadata(data)
    assert fmt is FontFormat.WOFF


def test_stripped_copyright_is_none() -> None:
    data = build_test_font(copyright=None, license_description=None)
    meta, _fmt = read_font_metadata(data)
    assert meta.copyright is None
    assert meta.license_description is None
    assert meta.owner == "Demo Owner"


def test_glyph_count_reflects_subset_size() -> None:
    small = build_test_font(extra_glyphs=0)
    full = build_test_font(extra_glyphs=200)
    assert read_font_metadata(small)[0].num_glyphs == 3
    assert read_font_metadata(full)[0].num_glyphs == 203


def test_invalid_bytes_raise() -> None:
    with pytest.raises(FontReadError):
        read_font_metadata(b"this is not a font")


def test_corrupt_table_raises_not_crashes() -> None:
    # A font whose sfnt directory points a table past EOF constructs fine under
    # lazy loading but fails when the table is decompiled. That must surface as
    # FontReadError, not an uncaught AssertionError/struct.error that aborts the scan.
    data = bytearray(build_test_font())
    num_tables = int.from_bytes(data[4:6], "big")
    for i in range(num_tables):
        rec = 12 + i * 16  # 12-byte header, 16-byte table records
        if bytes(data[rec : rec + 4]) == b"name":
            data[rec + 8 : rec + 12] = (len(data) + 1_000_000).to_bytes(4, "big")  # bad offset
            break
    with pytest.raises(FontReadError):
        read_font_metadata(bytes(data))
