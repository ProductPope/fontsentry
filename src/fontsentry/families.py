"""Normalize a font-family name to its *base family* — the name with weight and
style variants folded away, so `metropolis`, `metropolis-bold`, and
`OpenSans-Regular` group with their plain forms.

Width (Condensed / Narrow / Expanded) is deliberately kept: it marks a
genuinely different, often separately-licensed design, not just a weight.

This is a heuristic — it won't tame every vendor's naming (`apds2 XYZ Sans`),
but it collapses the common `Family-Weight` / `FamilyWeight` shapes.
"""

from __future__ import annotations

import re

# Trailing tokens that denote a weight, style, or build variant — stripped from
# the end of the name. Width keywords are intentionally NOT here.
_VARIANT_TOKENS = frozenset(
    {
        # weights
        "thin",
        "hairline",
        "extralight",
        "ultralight",
        "light",
        "semilight",
        "book",
        "regular",
        "normal",
        "roman",
        "text",
        "medium",
        "semibold",
        "demibold",
        "demi",
        "semi",
        "bold",
        "extrabold",
        "ultrabold",
        "ultra",
        "extra",
        "heavy",
        "black",
        "fat",
        # styles
        "italic",
        "oblique",
        "ital",
        "it",
        # build/vendor suffixes
        "mt",
        "web",
    }
)

# Insert a space at: lower/digit -> upper, letter <-> digit, and the end of a
# run of capitals before a capitalized word (so "XYZSans" -> "XYZ Sans").
_CAMEL = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])"
    r"|(?<=[A-Za-z])(?=[0-9])"
    r"|(?<=[0-9])(?=[A-Za-z])"
    r"|(?<=[A-Z])(?=[A-Z][a-z])"
)
_SEPARATORS = re.compile(r"[-_]+")


def _tokenize(name: str) -> list[str]:
    spaced = _CAMEL.sub(" ", _SEPARATORS.sub(" ", name))
    return spaced.split()


def _is_variant(token: str) -> bool:
    low = token.lower()
    if low in _VARIANT_TOKENS:
        return True
    # A numeric weight like 400 / 700.
    return low.isdigit() and 100 <= int(low) <= 900


def base_family(name: str) -> str:
    """Return the base family name (original casing of the kept tokens). Falls
    back to the trimmed input if stripping would remove everything."""
    tokens = _tokenize(name)
    while tokens and _is_variant(tokens[-1]):
        tokens.pop()
    return " ".join(tokens) if tokens else name.strip()


def group_key(name: str) -> str:
    """A space/punctuation/case-insensitive key for grouping — `Open Sans` and
    `OpenSans` collapse to the same key."""
    return re.sub(r"[^a-z0-9]", "", base_family(name).lower())
