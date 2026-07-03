"""Registry suppression: domain coverage, max_domains, expiry, matching."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fontsentry.models import AggregatedFont, FindingStatus, Registry, RegistryEntry
from fontsentry.registry.registry import (
    Suppression,
    evaluate_suppression,
    find_entry,
    is_expired,
    validate_registry,
)

NOW = date(2026, 6, 30)


def _entry(**kw: object) -> RegistryEntry:
    base: dict[str, object] = {
        "owner": "Acme Type",
        "family": "Commercial Sans",
        "license_type": "Web",
        "allowed_domains": ["example.com"],
        "valid_until": date(2030, 1, 1),
    }
    base.update(kw)
    return RegistryEntry(**base)


def _agg(
    domains: list[str], *, owner: str = "Acme Type", family: str = "Commercial Sans"
) -> AggregatedFont:
    return AggregatedFont(family=family, owner=owner, domains=sorted(domains))


def _suppress(agg: AggregatedFont, entry: RegistryEntry) -> Suppression:
    return evaluate_suppression(agg, Registry(entries=[entry]), NOW)


def test_subdomain_is_covered_by_parent_license() -> None:
    # A license for example.com covers www.example.com (dot-bounded subdomain).
    s = _suppress(_agg(["www.example.com"]), _entry())
    assert s.status is FindingStatus.RESOLVED


def test_apex_plus_subdomain_count_as_one_licensed_domain() -> None:
    # example.com + www.example.com under a max_domains:1 license is ONE domain.
    s = _suppress(_agg(["example.com", "www.example.com"]), _entry(max_domains=1))
    assert s.status is FindingStatus.RESOLVED


def test_distinct_registrable_domains_still_trip_max_domains() -> None:
    e = _entry(allowed_domains=["example.com", "other.com"], max_domains=1)
    s = _suppress(_agg(["example.com", "other.com"]), e)
    assert s.status is FindingStatus.OPEN
    assert "max_domains" in (s.reason or "")


def test_uncovered_domain_is_open() -> None:
    s = _suppress(_agg(["example.com", "evil.test"]), _entry())
    assert s.status is FindingStatus.OPEN
    assert "evil.test" in (s.reason or "")
    assert "example.com" not in (s.reason or "")  # only the uncovered one is listed


def test_lookalike_host_is_not_covered() -> None:
    # notexample.com must NOT be covered by an example.com license (no dot boundary).
    s = _suppress(_agg(["notexample.com"]), _entry())
    assert s.status is FindingStatus.OPEN


def test_wildcard_covers_any_domain() -> None:
    s = _suppress(_agg(["anything.test", "else.test"]), _entry(allowed_domains=["*"]))
    assert s.status is FindingStatus.RESOLVED


def test_expiry_boundary_valid_on_the_expiry_date() -> None:
    # valid_until == now is NOT expired (strict <).
    assert is_expired(_entry(valid_until=NOW), NOW) is False
    s = _suppress(_agg(["example.com"]), _entry(valid_until=NOW))
    assert s.status is FindingStatus.RESOLVED


def test_expired_takes_precedence_over_domain_check() -> None:
    e = _entry(valid_until=date(2020, 1, 1), allowed_domains=["other.com"])
    s = _suppress(_agg(["example.com"]), e)
    assert s.status is FindingStatus.OPEN
    assert "expired" in (s.reason or "")


def test_find_entry_first_match_wins() -> None:
    reg = Registry(
        entries=[
            _entry(license_type="First"),
            _entry(license_type="Second"),
        ]
    )
    assert find_entry(reg, "Acme Type", "Commercial Sans").license_type == "First"  # type: ignore[union-attr]


def test_find_entry_case_insensitive_no_false_none_match() -> None:
    reg = Registry(entries=[_entry()])
    assert find_entry(reg, "acme type", "COMMERCIAL SANS") is not None
    # A None owner must not match an entry (which always has a non-empty owner).
    assert find_entry(reg, None, "Commercial Sans") is None


def test_no_matching_entry_is_open() -> None:
    s = evaluate_suppression(_agg(["example.com"]), Registry(), NOW)
    assert s.status is FindingStatus.OPEN
    assert s.entry is None


def test_validate_registry_reports_missing_then_passes(tmp_path: Path) -> None:
    proofs = tmp_path / "proofs"
    proofs.mkdir()
    reg = Registry(entries=[_entry(proof_path="p.pdf")])
    errors = validate_registry(reg, proofs)
    assert errors and "proof" in errors[0]
    (proofs / "p.pdf").write_bytes(b"%PDF-1.4")
    assert validate_registry(reg, proofs) == []
