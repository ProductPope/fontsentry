"""Verdict engine: aggregation, deterministic license verdicts, privacy axis."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fontsentry import config
from fontsentry.models import (
    DetectedFont,
    EmbeddingMethod,
    FontFormat,
    FontMetadata,
    LicenseVerdict,
    PrivacyClass,
    Registry,
    RegistryEntry,
    RulesConfig,
)
from fontsentry.risk.engine import aggregate, evaluate, validate_rules

NOW = date(2026, 6, 30)


@pytest.fixture
def rules(repo_root: Path) -> RulesConfig:
    return config.load_rules(repo_root / "config" / "rules.example.yaml")


def _font(
    *,
    family: str = "Commercial Sans",
    embedding: EmbeddingMethod = EmbeddingMethod.SELF_HOSTED,
    fmt: FontFormat = FontFormat.TTF,
    page: str = "https://example.com/",
    owner: str | None = "Acme Type",
    copyright: str | None = "Copyright 2026 Acme Type",
    license_desc: str | None = "Desktop license.",
    num_glyphs: int | None = 800,
    applied: bool = True,
    fs_type: int | None = None,
) -> DetectedFont:
    return DetectedFont(
        family=family,
        embedding=embedding,
        font_format=fmt,
        source_page=page,
        font_url=f"{page}fonts/{family.replace(' ', '').lower()}.{fmt.value}",
        metadata=FontMetadata(
            family_name=family,
            owner=owner,
            copyright=copyright,
            license_description=license_desc,
            num_glyphs=num_glyphs,
            fs_type=fs_type,
        ),
        applied=applied,
    )


def test_aggregate_merges_across_domains() -> None:
    fonts = [
        _font(page="https://example.com/"),
        _font(page="https://example.com/about"),
        _font(page="https://example.org/"),
    ]
    aggs = aggregate(fonts)
    assert len(aggs) == 1
    assert aggs[0].domains == ["example.com", "example.org"]
    assert aggs[0].occurrences == 3


def test_commercial_unregistered_is_needs_check(rules: RulesConfig) -> None:
    finding = evaluate([_font()], rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.NEEDS_CHECK
    assert finding.needs_action is True
    # Evidence notes inform but don't decide.
    assert any("desktop font format" in n for n in finding.evidence_notes)


def test_unused_font_adds_evidence_note(rules: RulesConfig) -> None:
    finding = evaluate([_font(applied=False)], rules, Registry(), NOW)[0]
    assert finding.applied is False
    assert any("not applied" in n for n in finding.evidence_notes)


def test_registry_match_is_ok(rules: RulesConfig) -> None:
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Acme Type",
                family="Commercial Sans",
                license_type="Web",
                allowed_domains=["example.com"],
                valid_until=date(2030, 1, 1),
            )
        ]
    )
    finding = evaluate([_font()], rules, registry, NOW)[0]
    assert finding.license_verdict is LicenseVerdict.OK
    assert "covered by your license" in finding.license_reason
    assert finding.needs_action is False


def test_max_domains_exceeded_is_violation(rules: RulesConfig) -> None:
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Acme Type",
                family="Commercial Sans",
                license_type="Web, single domain",
                allowed_domains=["example.com", "example.org"],
                max_domains=1,
                valid_until=date(2030, 1, 1),
            )
        ]
    )
    fonts = [_font(page="https://example.com/"), _font(page="https://example.org/")]
    finding = evaluate(fonts, rules, registry, NOW)[0]
    assert finding.license_verdict is LicenseVerdict.VIOLATION
    assert "max_domains" in finding.license_reason
    assert finding.domain_count == 2


def test_expired_license_is_violation(rules: RulesConfig) -> None:
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Acme Type",
                family="Commercial Sans",
                license_type="Web",
                allowed_domains=["example.com"],
                valid_until=date(2025, 1, 1),
            )
        ]
    )
    finding = evaluate([_font()], rules, registry, NOW)[0]
    assert finding.license_verdict is LicenseVerdict.VIOLATION
    assert "expired" in finding.license_reason


def test_self_host_prohibited_is_violation(rules: RulesConfig) -> None:
    fonts = [_font(family="Atlas Grotesk Private", owner="Meridian Letterworks")]
    finding = evaluate(fonts, rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.VIOLATION
    assert "self-hosting" in finding.license_reason


def test_restricted_fstype_is_violation(rules: RulesConfig) -> None:
    # OS/2 fsType Restricted-License bit set: the foundry forbids embedding.
    finding = evaluate([_font(fs_type=0x0002)], rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.VIOLATION
    assert "fsType" in finding.license_reason


def test_installable_fstype_not_flagged(rules: RulesConfig) -> None:
    finding = evaluate([_font(fs_type=0)], rules, Registry(), NOW)[0]
    assert finding.license_verdict is not LicenseVerdict.VIOLATION


def test_missing_license_string_adds_evidence(rules: RulesConfig) -> None:
    finding = evaluate([_font(copyright=None, license_desc=None)], rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.NEEDS_CHECK
    assert any("no license or copyright" in n for n in finding.evidence_notes)


def test_open_family_is_ok(rules: RulesConfig) -> None:
    fonts = [
        _font(
            family="Font Awesome 5 Free",
            owner=None,
            embedding=EmbeddingMethod.OTHER_CDN,
            fmt=FontFormat.WOFF2,
            copyright="Copyright (c) Font Awesome",
            license_desc=None,
            num_glyphs=154,
        )
    ]
    finding = evaluate(fonts, rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.OK
    assert "open" in finding.license_reason


def test_paid_tier_in_name_is_violation(rules: RulesConfig) -> None:
    fonts = [
        _font(
            family="Font Awesome 6 Pro",
            owner=None,
            embedding=EmbeddingMethod.OTHER_CDN,
            fmt=FontFormat.WOFF2,
            copyright="Copyright (c) Font Awesome",
            license_desc=None,
            num_glyphs=154,
        )
    ]
    finding = evaluate(fonts, rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.VIOLATION
    assert "paid tier" in finding.license_reason


def test_unknown_delivery_is_needs_check(rules: RulesConfig) -> None:
    # A font referenced but not observed (UNKNOWN delivery) must not read as OK.
    font = DetectedFont(
        family="Injected Sans",
        embedding=EmbeddingMethod.UNKNOWN,
        source_page="https://example.com/",
    )
    finding = evaluate([font], rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.NEEDS_CHECK
    assert any("delivery was not observed" in n for n in finding.evidence_notes)


def test_system_font_is_ok(rules: RulesConfig) -> None:
    system = DetectedFont(
        family="Georgia", embedding=EmbeddingMethod.SYSTEM, source_page="https://example.com/"
    )
    finding = evaluate([system], rules, Registry(), NOW)[0]
    assert finding.license_verdict is LicenseVerdict.OK
    assert "system" in finding.license_reason


def test_privacy_axis_independent_of_license(rules: RulesConfig) -> None:
    google = _font(
        family="Roboto", owner=None, embedding=EmbeddingMethod.GOOGLE_FONTS, fmt=FontFormat.WOFF2
    )
    finding = evaluate([google], rules, Registry(), NOW)[0]
    assert finding.privacy is PrivacyClass.THIRD_PARTY_API
    assert finding.needs_action is True  # third-party delivery needs action regardless


def test_validate_rules_clean(rules: RulesConfig) -> None:
    assert validate_rules(rules) == []


def test_validate_rules_flags_unknown_values() -> None:
    bad = RulesConfig(paid_cdns=["not_a_method"], desktop_formats=["ttf", "xyz"])
    errors = validate_rules(bad)
    assert any("not_a_method" in e for e in errors)
    assert any("xyz" in e for e in errors)
