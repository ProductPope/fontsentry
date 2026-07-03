"""Risk engine: aggregation, scoring, cross-domain rule, bands, validation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fontsentry import config
from fontsentry.models import (
    BandThresholds,
    DetectedFont,
    EmbeddingMethod,
    FindingStatus,
    FontFormat,
    FontMetadata,
    PrivacyClass,
    Registry,
    RegistryEntry,
    RiskBand,
    Rule,
    RuleCondition,
    RulesConfig,
    Scoring,
)
from fontsentry.risk.engine import (
    EngineError,
    _classify_privacy,
    aggregate,
    band_for,
    evaluate,
    validate_rules,
)

NOW = date(2026, 6, 30)


def _rules(
    *, max_raw: int = 90, medium: int = 30, high: int = 60, rules: list[Rule] | None = None
) -> RulesConfig:
    return RulesConfig(
        scoring=Scoring(max_raw=max_raw, bands=BandThresholds(medium=medium, high=high)),
        rules=rules
        if rules is not None
        else [
            Rule(
                id="fmt",
                description="format on web",
                weight=100,
                confidence=1.0,
                when=RuleCondition(type="format_on_web", params={"formats": ["ttf"]}),
            )
        ],
    )


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


def test_privacy_axis_is_independent_of_license(rules: RulesConfig) -> None:
    # Google Fonts served via the API is freely licensed but a GDPR concern: the
    # privacy axis must flag it as third-party regardless of the license score.
    google = _font(
        family="Roboto",
        owner=None,
        embedding=EmbeddingMethod.GOOGLE_FONTS,
        fmt=FontFormat.WOFF2,
    )
    finding = evaluate([google], rules, Registry(), NOW)[0]
    assert finding.privacy is PrivacyClass.THIRD_PARTY_API

    # Self-hosted delivery is clean on the privacy axis.
    self_hosted = evaluate([_font(embedding=EmbeddingMethod.SELF_HOSTED)], rules, Registry(), NOW)[
        0
    ]
    assert self_hosted.privacy is PrivacyClass.SELF_HOSTED


def test_privacy_mixed_when_self_hosted_and_third_party() -> None:
    fonts = [
        _font(family="Roboto", page="https://a.com/", embedding=EmbeddingMethod.GOOGLE_FONTS),
        _font(family="Roboto", page="https://a.com/b", embedding=EmbeddingMethod.SELF_HOSTED),
    ]
    assert aggregate(fonts)[0].privacy is PrivacyClass.MIXED


def test_privacy_not_applicable_for_system_font() -> None:
    assert aggregate([_font(embedding=EmbeddingMethod.SYSTEM)])[0].privacy is (
        PrivacyClass.NOT_APPLICABLE
    )


def test_score_is_clamped_to_100_exactly() -> None:
    # raw = 100, max_raw = 10 -> 100*100/10 = 1000 -> clamped to 100 (HIGH).
    findings = evaluate([_font()], _rules(max_raw=10), Registry(), NOW)
    assert findings[0].score == 100
    assert findings[0].band is RiskBand.HIGH


def test_triggered_rule_points_are_weight_times_confidence() -> None:
    r = _rules(
        rules=[
            Rule(
                id="fmt",
                description="d",
                weight=30,
                confidence=0.85,
                when=RuleCondition(type="format_on_web", params={"formats": ["ttf"]}),
            )
        ]
    )
    finding = evaluate([_font()], r, Registry(), NOW)[0]
    assert finding.triggered_rules[0].points == 25.5


def test_not_applied_halves_and_rebands_exactly() -> None:
    # raw 60 (weight 60, conf 1, max_raw 100) -> score 60 (HIGH); applied=False
    # halves to 30 and rebands to MEDIUM.
    r = _rules(
        max_raw=100,
        rules=[
            Rule(
                id="fmt",
                description="d",
                weight=60,
                confidence=1.0,
                when=RuleCondition(type="format_on_web", params={"formats": ["ttf"]}),
            )
        ],
    )
    applied = evaluate([_font()], r, Registry(), NOW)[0]
    unused = evaluate([_font(applied=False)], r, Registry(), NOW)[0]
    assert (applied.score, applied.band) == (60, RiskBand.HIGH)
    assert (unused.score, unused.band) == (30, RiskBand.MEDIUM)


def test_findings_sorted_by_score_then_family() -> None:
    fonts = [
        _font(family="Zeta", owner="A", page="https://z.com/"),
        _font(family="alpha", owner="A", page="https://a.com/"),
        _font(family="Beta", owner="A", page="https://b.com/"),
    ]
    # All three trip the same rule -> equal score -> pure case-insensitive family sort.
    order = [f.family for f in evaluate(fonts, _rules(), Registry(), NOW)]
    assert order == ["alpha", "Beta", "Zeta"]


def test_aggregate_page_count_and_url_cap() -> None:
    pages = [f"https://example.com/p{i}" for i in range(7)]
    fonts = [_font(family="Acme Sans", owner="Acme Type", page=p) for p in pages]
    agg = aggregate(fonts)[0]
    assert agg.owner == "Acme Type"
    assert agg.page_count == 7
    assert agg.occurrences == 7
    assert len(agg.example_urls) == 5 and agg.example_urls == sorted(agg.example_urls)


def test_aggregate_splits_same_family_by_owner() -> None:
    # A benign/free owner on one page must not merge with a commercial owner on
    # another for the same family string (FN-2: prevents owner masking).
    fonts = [
        _font(family="Helvetica", owner="Public Glyphs Foundation"),
        _font(family="Helvetica", owner="Meridian Letterworks"),
    ]
    assert {a.owner for a in aggregate(fonts)} == {
        "Public Glyphs Foundation",
        "Meridian Letterworks",
    }


def test_aggregate_folds_case_and_whitespace() -> None:
    fonts = [
        _font(family="Acme Sans"),
        _font(family=" acme sans "),
        _font(family="ACME SANS"),
    ]
    assert len(aggregate(fonts)) == 1


def test_adding_a_triggering_rule_never_lowers_score() -> None:
    base = _rules(
        rules=[
            Rule(
                id="fmt",
                description="d",
                weight=30,
                confidence=0.85,
                when=RuleCondition(type="format_on_web", params={"formats": ["ttf"]}),
            )
        ]
    )
    extra = _rules(
        rules=[
            *base.rules,
            Rule(
                id="sub",
                description="d",
                weight=5,
                confidence=0.2,
                when=RuleCondition(type="subset_signal", params={"max_glyphs": 10000}),
            ),
        ]
    )
    f = _font(fmt=FontFormat.WOFF2, num_glyphs=50)
    assert (
        evaluate([f], extra, Registry(), NOW)[0].score
        >= evaluate([f], base, Registry(), NOW)[0].score
    )


def test_band_for_exact_boundaries() -> None:
    r = _rules(medium=30, high=60)
    assert band_for(29, r) is RiskBand.LOW
    assert band_for(30, r) is RiskBand.MEDIUM
    assert band_for(59, r) is RiskBand.MEDIUM
    assert band_for(60, r) is RiskBand.HIGH


def test_classify_privacy_table() -> None:
    E = EmbeddingMethod
    from fontsentry.models import PrivacyClass as P

    assert _classify_privacy({E.GOOGLE_FONTS}) is P.THIRD_PARTY_API
    assert _classify_privacy({E.SELF_HOSTED}) is P.SELF_HOSTED
    assert _classify_privacy({E.GOOGLE_FONTS, E.SELF_HOSTED}) is P.MIXED
    assert _classify_privacy({E.ADOBE_FONTS, E.MONOTYPE}) is P.THIRD_PARTY_API
    assert _classify_privacy({E.SYSTEM}) is P.NOT_APPLICABLE
    assert _classify_privacy({E.SYSTEM, E.SELF_HOSTED}) is P.SELF_HOSTED
    assert _classify_privacy(set()) is P.NOT_APPLICABLE


def test_hard_signal_is_not_halved_when_unapplied(rules: RulesConfig) -> None:
    # An expired license is a hard violation: serving-but-not-applying it must not
    # halve the score below the applied case (FN-3).
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Acme Type",
                family="Commercial Sans",
                license_type="Web",
                allowed_domains=["example.com"],
                valid_until=date(2020, 1, 1),
            )
        ]
    )
    applied = evaluate([_font()], rules, registry, NOW)[0]
    unused = evaluate([_font(applied=False)], rules, registry, NOW)[0]
    assert "expired-license" in {t.id for t in applied.triggered_rules}
    assert unused.score == applied.score  # hard signal -> no halving


def test_expired_entry_does_not_silence_commercial_rule(rules: RulesConfig) -> None:
    # An expired/non-covering entry is not valid coverage, so the commercial
    # signal still fires (FN-4) rather than being silenced by entry existence.
    registry = Registry(
        entries=[
            RegistryEntry(
                owner="Acme Type",
                family="Commercial Sans",
                license_type="Web",
                allowed_domains=["example.com"],
                valid_until=date(2020, 1, 1),
            )
        ]
    )
    fired = {t.id for t in evaluate([_font()], rules, registry, NOW)[0].triggered_rules}
    assert "commercial-no-registry" in fired
    assert "expired-license" in fired


def test_valid_entry_still_suppresses_commercial(rules: RulesConfig) -> None:
    # Sanity: a *valid* entry (covered) still silences the commercial rule.
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
    assert finding.status is FindingStatus.RESOLVED
    assert "commercial-no-registry" not in {t.id for t in finding.triggered_rules}


def test_validate_rules_clean(rules: RulesConfig) -> None:
    assert validate_rules(rules) == []


def test_unknown_predicate_type_detected(rules: RulesConfig) -> None:
    rules.rules[0].when.type = "does_not_exist"
    errors = validate_rules(rules)
    assert errors and "does_not_exist" in errors[0]
    with pytest.raises(EngineError):
        evaluate([_font()], rules, Registry(), NOW)
