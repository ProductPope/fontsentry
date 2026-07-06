"""Base-family normalization: folding weight/style variants into one group."""

from __future__ import annotations

import pytest

from fontsentry.families import base_family, group_key


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("metropolis", "metropolis"),
        ("metropolis-bold", "metropolis"),
        ("metropolis-extra-bold", "metropolis"),
        ("OpenSans-Regular", "Open Sans"),
        ("OpenSans-Medium", "Open Sans"),
        ("Open Sans", "Open Sans"),
        ("Roboto-Black", "Roboto"),
        ("Montserrat thin", "Montserrat"),
        ("Lato-Regular", "Lato"),
        ("Barlow Cond Web", "Barlow Cond"),  # width kept, "web" dropped
        ("ArialRoundedMTBold", "Arial Rounded"),
        ("Noto Sans", "Noto Sans"),  # "sans" is part of the name, not a weight
    ],
)
def test_base_family(name: str, expected: str) -> None:
    assert base_family(name) == expected


def test_variants_share_a_group_key() -> None:
    names = ["metropolis", "metropolis-bold", "metropolis-extra-bold"]
    assert len({group_key(n) for n in names}) == 1


def test_spacing_differences_collapse() -> None:
    # "Open Sans", "OpenSans-Regular" -> same group despite the space.
    assert group_key("Open Sans") == group_key("OpenSans-Regular")


def test_width_stays_distinct() -> None:
    assert group_key("Barlow Cond") != group_key("Barlow")


def test_empty_strip_falls_back_to_input() -> None:
    # A name that is *only* a weight token keeps itself rather than vanishing.
    assert base_family("Bold") == "Bold"


@pytest.mark.parametrize(
    "name",
    ["metropolis-bold", "OpenSans-Regular", "Roboto Black", "Barlow Cond Web", "Noto Sans"],
)
def test_base_family_is_idempotent(name: str) -> None:
    once = base_family(name)
    assert base_family(once) == once
    assert group_key(once) == group_key(name)
