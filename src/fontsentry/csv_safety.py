"""CSV formula-injection defense shared by every CSV writer.

Cells starting with ``=``, ``+``, ``-``, ``@``, a tab, or a carriage return are
interpreted as formulas by spreadsheet apps (CSV-injection / DDE). Content that
can be influenced by crawled sites — font metadata, URLs, registry fields fed
from detection suggestions — must be neutralized with a leading apostrophe on
export. Round-trip importers (the registry CSV) strip the same apostrophe back
off, so exported data survives an export → import cycle unchanged.
"""

from __future__ import annotations

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize_cell(value: object) -> str:
    """Prefix a formula-looking cell with an apostrophe for spreadsheet safety."""

    text = "" if value is None else str(value)
    return "'" + text if text[:1] in FORMULA_PREFIXES else text


def restore_cell(text: str) -> str:
    """Undo :func:`neutralize_cell` on a round-tripped cell.

    Only the exact escape is reversed (apostrophe followed by a formula prefix);
    any other leading apostrophe is user data and passes through untouched.
    """

    if text[:1] == "'" and text[1:2] in FORMULA_PREFIXES:
        return text[1:]
    return text
