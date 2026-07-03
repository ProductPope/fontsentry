"""Risk engine: aggregation, scoring, cross-domain rule, bands, validation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fontsentry import config
from fontsentry.models import (
    DetectedFont,
    EmbeddingMethod,
    FindingStatus,
    FontFormat,
    FontMetadata,
    Registry,
    RegistryEntry,
    RiskBand,
    RulesConfig,
)
from fontsentry.risk.engine import EngineError, aggregate, evaluate, validate_rules

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
        ),
        applied=applied,
    )


def test_declared_but_unused_font_scored_lower(rules: RulesConfig) -> None:
    used = evaluate([_font()], rules, Registry(), NOW)[0]
    unused = evaluate([_font(applied=False)], rules, Registry(), NOW)[0]
    assert used.applied is True
    assert unused.applied is False
    assert used.score > 0
    assert unused.score < used.score  # halved because it's served but not applied


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


def test_desktop_format_and_commercial_rules_fire(rules: RulesConfig) -> None:
    findings = evaluate([_font()], rules, Registry(), NOW)
    assert len(findings) == 1
    fired = {t.id for t in findings[0].triggered_rules}
    assert "desktop-format-on-web" in fired
    assert "commercial-no-registry" in fired
    assert findings[0].status is FindingStatus.OPEN
    assert findings[0].score > 0


def test_registry_match_suppresses(rules: RulesConfig) -> None:
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
    findings = evaluate([_font()], rules, registry, NOW)
    assert findings[0].status is FindingStatus.RESOLVED
    # With a matching entry, the "no registry" rule must not fire.
    assert "commercial-no-registry" not in {t.id for t in findings[0].triggered_rules}


def test_max_domains_rule_is_cross_domain(rules: RulesConfig) -> None:
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
    findings = evaluate(fonts, rules, registry, NOW)
    fired = {t.id for t in findings[0].triggered_rules}
    assert "max-domains-exceeded" in fired
    assert findings[0].status is FindingStatus.OPEN
    assert findings[0].domain_count == 2


def test_expired_license_rule_fires(rules: RulesConfig) -> None:
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
    findings = evaluate([_font()], rules, registry, NOW)
    fired = {t.id for t in findings[0].triggered_rules}
    assert "expired-license" in fired
    assert findings[0].status is FindingStatus.OPEN


def test_missing_copyright_rule_fires(rules: RulesConfig) -> None:
    fonts = [_font(copyright=None, license_desc=None)]
    findings = evaluate(fonts, rules, Registry(), NOW)
    assert "missing-copyright" in {t.id for t in findings[0].triggered_rules}


def test_paid_cdn_rule_fires(rules: RulesConfig) -> None:
    fonts = [_font(embedding=EmbeddingMethod.ADOBE_FONTS, fmt=FontFormat.WOFF2)]
    findings = evaluate(fonts, rules, Registry(), NOW)
    assert "paid-cdn-no-registry" in {t.id for t in findings[0].triggered_rules}


def test_score_clamped_and_banded(rules: RulesConfig) -> None:
    # Self-hosted prohibited owner + commercial + desktop format + expired => high.
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Meridian Letterworks",
                family="Atlas Grotesk Private",
                license_type="Web",
                allowed_domains=["example.com"],
                valid_until=date(2025, 1, 1),
            )
        ]
    )
    fonts = [
        _font(
            family="Atlas Grotesk Private",
            owner="Meridian Letterworks",
            page="https://example.com/",
        )
    ]
    findings = evaluate(fonts, rules, registry, NOW)
    assert 0 <= findings[0].score <= 100
    assert findings[0].band in (RiskBand.MEDIUM, RiskBand.HIGH)


def test_open_family_not_flagged_commercial(rules: RulesConfig) -> None:
    # Font Awesome Free is OFL-licensed but ships without a license string, so it
    # would otherwise trip commercial-no-registry. The open_families allowlist
    # keeps it out of that rule -> it lands LOW, not MEDIUM.
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
    fired = {t.id for t in finding.triggered_rules}
    assert "commercial-no-registry" not in fired
    assert finding.band is RiskBand.LOW


def test_paid_tier_in_name_flags_font_awesome_pro(rules: RulesConfig) -> None:
    # The Pro tier is paid and per-domain: it fires paid-tier-in-name and lands
    # at least MEDIUM, distinctly above the Free tier.
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
    fired = {t.id for t in finding.triggered_rules}
    assert "paid-tier-in-name" in fired
    assert finding.band in (RiskBand.MEDIUM, RiskBand.HIGH)


def test_validate_rules_clean(rules: RulesConfig) -> None:
    assert validate_rules(rules) == []


def test_unknown_predicate_type_detected(rules: RulesConfig) -> None:
    rules.rules[0].when.type = "does_not_exist"
    errors = validate_rules(rules)
    assert errors and "does_not_exist" in errors[0]
    with pytest.raises(EngineError):
        evaluate([_font()], rules, Registry(), NOW)
