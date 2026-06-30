"""Registry matching and suppression decisions."""

from __future__ import annotations

from datetime import date

from fontsentry.models import AggregatedFont, FindingStatus, Registry, RegistryEntry
from fontsentry.registry.registry import evaluate_suppression, find_entry, is_expired

NOW = date(2026, 6, 30)


def _registry() -> Registry:
    return Registry(
        entries=[
            RegistryEntry(
                foundry="Meridian Letterworks",
                family="Atlas Grotesk Private",
                license_type="Web, single domain",
                allowed_domains=["example.com"],
                max_domains=1,
                valid_until=date(2027, 12, 31),
            ),
        ]
    )


def _agg(domains: list[str], foundry: str = "Meridian Letterworks") -> AggregatedFont:
    return AggregatedFont(family="Atlas Grotesk Private", foundry=foundry, domains=domains)


def test_find_entry_case_insensitive() -> None:
    entry = find_entry(_registry(), "meridian letterworks", "ATLAS GROTESK PRIVATE")
    assert entry is not None
    assert entry.family == "Atlas Grotesk Private"


def test_covered_font_is_resolved() -> None:
    result = evaluate_suppression(_agg(["example.com"]), _registry(), NOW)
    assert result.status is FindingStatus.RESOLVED
    assert result.entry is not None


def test_no_registry_entry_is_open() -> None:
    result = evaluate_suppression(_agg(["example.com"], foundry="Unknown Co"), _registry(), NOW)
    assert result.status is FindingStatus.OPEN
    assert result.entry is None
    assert "no matching license" in (result.reason or "")


def test_domain_not_covered_is_open() -> None:
    result = evaluate_suppression(_agg(["other.com"]), _registry(), NOW)
    assert result.status is FindingStatus.OPEN
    assert "not covered" in (result.reason or "")


def test_max_domains_exceeded_is_open() -> None:
    reg = _registry()
    reg.entries[0].allowed_domains = ["example.com", "example.org"]
    result = evaluate_suppression(_agg(["example.com", "example.org"]), reg, NOW)
    assert result.status is FindingStatus.OPEN
    assert "max_domains" in (result.reason or "")


def test_expired_license_is_open() -> None:
    reg = _registry()
    reg.entries[0].valid_until = date(2025, 1, 1)
    result = evaluate_suppression(_agg(["example.com"]), reg, NOW)
    assert result.status is FindingStatus.OPEN
    assert "expired" in (result.reason or "")


def test_is_expired() -> None:
    entry = _registry().entries[0]
    assert is_expired(entry, date(2028, 1, 1)) is True
    assert is_expired(entry, date(2026, 1, 1)) is False
