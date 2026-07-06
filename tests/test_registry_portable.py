"""CSV import/export for the registry: round-trip fidelity and lenient parsing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fontsentry.models import Registry, RegistryEntry
from fontsentry.registry.portable import registry_from_csv, registry_to_csv


def _entry(**kw: object) -> RegistryEntry:
    base: dict[str, object] = {"owner": "Acme", "family": "Sans", "license_type": "Web"}
    base.update(kw)
    return RegistryEntry(**base)


def test_csv_round_trip_preserves_fields() -> None:
    registry = Registry(
        entries=[
            _entry(
                owner="Acme Type",
                family="Commercial Sans",
                allowed_domains=["example.com", "www.example.com"],
                max_domains=3,
                valid_until=date(2030, 1, 1),
                proof_path=Path("acme.pdf"),
                notes="renewed 2026",
            ),
            _entry(owner="Beta", family="Serif"),  # sparse row (optionals empty)
        ]
    )
    parsed, errors = registry_from_csv(registry_to_csv(registry))
    assert errors == []
    assert parsed == registry


def test_csv_import_pipes_domains_and_iso_date() -> None:
    text = (
        "owner,family,license_type,allowed_domains,max_domains,valid_until\n"
        "Acme,Sans,Web,a.com|b.com,2,2031-06-30\n"
    )
    parsed, errors = registry_from_csv(text)
    assert errors == []
    (entry,) = parsed.entries
    assert entry.allowed_domains == ["a.com", "b.com"]
    assert entry.max_domains == 2
    assert entry.valid_until == date(2031, 6, 30)


def test_csv_import_reports_bad_rows_and_keeps_good() -> None:
    text = (
        "owner,family,license_type,max_domains,valid_until\n"
        "Good,Sans,Web,,\n"
        "Bad,Serif,Web,notanumber,\n"  # max_domains not an int
        "AlsoBad,Mono,Web,,2026-13-40\n"  # invalid date
        "\n"  # blank line skipped
        "Good2,Slab,Web,,\n"
    )
    parsed, errors = registry_from_csv(text)
    assert {e.family for e in parsed.entries} == {"Sans", "Slab"}
    assert len(errors) == 2
    assert errors[0].startswith("row 3:")
    assert errors[1].startswith("row 4:")


def test_csv_import_missing_required_column() -> None:
    parsed, errors = registry_from_csv("owner,family\nAcme,Sans\n")
    assert parsed.entries == []
    assert errors and "license_type" in errors[0]


def test_csv_export_neutralizes_formula_cells() -> None:
    # Registry text fields can be fed from crawled font metadata, so a cell
    # starting with a formula character must not reach a spreadsheet raw
    # (CSV-injection / DDE). Regression: export previously wrote it verbatim.
    registry = Registry(entries=[_entry(owner="=CMD()", family="@Import", notes="+SUM(A1)")])
    text = registry_to_csv(registry)
    assert "'=CMD()" in text
    assert "'@Import" in text
    assert "'+SUM(A1)" in text
    assert "\n=CMD()" not in text and ",=CMD()" not in text


def test_csv_round_trip_preserves_formula_looking_values() -> None:
    # The neutralizing apostrophe is an export-side escape; import strips it,
    # so export -> import returns the exact original entry.
    registry = Registry(entries=[_entry(owner="=Weird Foundry", family="-Dash Sans")])
    parsed, errors = registry_from_csv(registry_to_csv(registry))
    assert errors == []
    assert parsed == registry


def test_csv_import_keeps_plain_apostrophe_prefix() -> None:
    # Only the exact escape (apostrophe + formula char) is reversed; an
    # apostrophe followed by anything else is user data and must survive.
    text = "owner,family,license_type\n'Acme,Sans,Web\n"
    parsed, errors = registry_from_csv(text)
    assert errors == []
    assert parsed.entries[0].owner == "'Acme"
