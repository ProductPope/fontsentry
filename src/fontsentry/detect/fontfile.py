"""Read font-file metadata (name table + format) with fonttools."""

from __future__ import annotations

from io import BytesIO

from fontTools.ttLib import TTFont, TTLibError

from fontsentry.models import FontFormat, FontMetadata

# name table IDs we care about (OpenType spec).
_NAME_COPYRIGHT = 0
_NAME_FAMILY = 1
_NAME_UNIQUE_ID = 3
_NAME_MANUFACTURER = 8
_NAME_DESIGNER = 9
_NAME_LICENSE_DESC = 13
_NAME_LICENSE_URL = 14
_NAME_TYPO_FAMILY = 16


class FontReadError(Exception):
    """Raised when font bytes cannot be parsed."""


def _format_of(font: TTFont) -> FontFormat:
    flavor = font.flavor
    if flavor == "woff2":
        return FontFormat.WOFF2
    if flavor == "woff":
        return FontFormat.WOFF
    if font.sfntVersion == "OTTO":
        return FontFormat.OTF
    if font.sfntVersion in ("\x00\x01\x00\x00", "true", "ttcf"):
        return FontFormat.TTF
    return FontFormat.UNKNOWN


def read_font_metadata(data: bytes) -> tuple[FontMetadata, FontFormat]:
    """Parse font bytes into :class:`FontMetadata` and a :class:`FontFormat`.

    Raises :class:`FontReadError` for unparseable input. Any individual name-table
    field may be ``None`` when absent or stripped.
    """

    try:
        font = TTFont(BytesIO(data), lazy=True, fontNumber=0)
    except (TTLibError, ValueError, OSError) as exc:
        raise FontReadError(f"could not parse font: {exc}") from exc

    try:
        name = font.get("name")

        def best(name_id: int) -> str | None:
            if name is None:
                return None
            value = name.getDebugName(name_id)
            return value or None

        num_glyphs: int | None = None
        if "maxp" in font:
            num_glyphs = int(font["maxp"].numGlyphs)

        metadata = FontMetadata(
            family_name=best(_NAME_TYPO_FAMILY) or best(_NAME_FAMILY),
            owner=best(_NAME_MANUFACTURER),
            designer=best(_NAME_DESIGNER),
            copyright=best(_NAME_COPYRIGHT),
            license_description=best(_NAME_LICENSE_DESC),
            license_url=best(_NAME_LICENSE_URL),
            unique_id=best(_NAME_UNIQUE_ID),
            num_glyphs=num_glyphs,
        )
        return metadata, _format_of(font)
    finally:
        font.close()
