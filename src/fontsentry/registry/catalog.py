"""A small catalog of well-known, publicly-available font families, used only to
seed autocomplete when adding a registry license — so a first-time user gets
suggestions before any audit has run and is less likely to mistype a name.

NOTE: this is the one place the repo carries real font/foundry names on purpose.
The brand-neutral rule (see CLAUDE.md) applies to demo data and default config;
this is a functional catalog the tool legitimately helps operators reference.
Owners are filled only where a well-known organization publishes the family.
"""

from __future__ import annotations

# (family, owner-or-None). Kept short and open-source-leaning; the operator can
# type anything — this only powers suggestions.
CATALOG: tuple[tuple[str, str | None], ...] = (
    ("Roboto", "Google"),
    ("Open Sans", "Google"),
    ("Noto Sans", "Google"),
    ("Noto Serif", "Google"),
    ("Rubik", "Google"),
    ("Material Icons", "Google"),
    ("Material Symbols", "Google"),
    ("Lato", None),
    ("Montserrat", None),
    ("Poppins", "Indian Type Foundry"),
    ("Inter", None),
    ("Work Sans", None),
    ("Nunito", None),
    ("Nunito Sans", None),
    ("Oswald", None),
    ("Raleway", None),
    ("Source Sans 3", "Adobe"),
    ("Source Serif 4", "Adobe"),
    ("Source Code Pro", "Adobe"),
    ("Fira Sans", "Mozilla"),
    ("Fira Code", "Mozilla"),
    ("PT Sans", "ParaType"),
    ("PT Serif", "ParaType"),
    ("Merriweather", None),
    ("Playfair Display", None),
    ("Ubuntu", "Canonical"),
    ("Ubuntu Mono", "Canonical"),
    ("IBM Plex Sans", "IBM"),
    ("IBM Plex Mono", "IBM"),
    ("IBM Plex Serif", "IBM"),
    ("Titillium Web", None),
    ("Barlow", None),
    ("Karla", None),
    ("Mulish", None),
    ("DM Sans", None),
    ("DM Serif Display", None),
    ("Space Grotesk", None),
    ("Manrope", None),
    ("Heebo", None),
    ("Cabin", None),
    ("Quicksand", None),
    ("Josefin Sans", None),
    ("Libre Franklin", None),
    ("Archivo", None),
    ("Bebas Neue", None),
    ("Dosis", None),
    ("Font Awesome", "Fonticons"),
    ("Font Awesome 5 Free", "Fonticons"),
    ("Font Awesome 6 Free", "Fonticons"),
)
