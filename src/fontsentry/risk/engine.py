"""The verdict engine: aggregate detected fonts, then classify each deterministically.

Aggregation runs over the *whole* crawl before classification, so cross-domain
facts (e.g. max_domains) see every domain a font appears on. Each font gets two
verdicts — license and privacy — from a fixed decision table (ADR 0003). No
weights, no thresholds; every verdict maps to an explicit if/then with a reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from fontsentry.families import base_family
from fontsentry.models import (
    AggregatedFont,
    DetectedFont,
    EmbeddingMethod,
    Finding,
    FindingStatus,
    FontFormat,
    FontMetadata,
    LicenseVerdict,
    PrivacyClass,
    Registry,
    RulesConfig,
)
from fontsentry.registry.registry import Suppression, evaluate_suppression
from fontsentry.risk import rules as clf


class EngineError(Exception):
    """Raised when the classification config is invalid."""


# Sort order: most-attention-worthy first.
_VERDICT_RANK = {
    LicenseVerdict.VIOLATION: 0,
    LicenseVerdict.NEEDS_CHECK: 1,
    LicenseVerdict.OK: 2,
}
_PRIVACY_RANK = {
    PrivacyClass.THIRD_PARTY_API: 0,
    PrivacyClass.MIXED: 0,
    PrivacyClass.SELF_HOSTED: 1,
    PrivacyClass.NOT_APPLICABLE: 1,
}


@dataclass
class _Accumulator:
    family: str
    owner: str | None = None
    domains: set[str] = field(default_factory=set)
    formats: set[FontFormat] = field(default_factory=set)
    embeddings: set[EmbeddingMethod] = field(default_factory=set)
    metadata: FontMetadata | None = None
    occurrences: int = 0
    pages: set[str] = field(default_factory=set)
    applied: bool = False


def _domain_of(url: str) -> str:
    return urlparse(url).hostname or url


# Delivery methods that route the font (and each visitor's IP) through a third
# party — the GDPR/RODO concern. SELF_HOSTED and SYSTEM stay on the site/device.
_THIRD_PARTY_EMBEDDINGS = frozenset(
    {
        EmbeddingMethod.GOOGLE_FONTS,
        EmbeddingMethod.ADOBE_FONTS,
        EmbeddingMethod.MONOTYPE,
        EmbeddingMethod.OTHER_CDN,
    }
)


def _classify_privacy(embeddings: set[EmbeddingMethod]) -> PrivacyClass:
    has_third_party = any(e in _THIRD_PARTY_EMBEDDINGS for e in embeddings)
    has_self_hosted = EmbeddingMethod.SELF_HOSTED in embeddings
    if has_third_party and has_self_hosted:
        return PrivacyClass.MIXED
    if has_third_party:
        return PrivacyClass.THIRD_PARTY_API
    if has_self_hosted:
        return PrivacyClass.SELF_HOSTED
    return PrivacyClass.NOT_APPLICABLE


def aggregate(fonts: list[DetectedFont]) -> list[AggregatedFont]:
    """Merge per-page detections into one identity per font family across all domains."""

    # Identity is (family, owner): the same family string with a different owner
    # is a different font, so a benign/free owner on one page can't mask a
    # commercial owner on another (that would silence the commercial signal).
    groups: dict[tuple[str, str], _Accumulator] = {}
    for font in fonts:
        owner = font.metadata.owner if font.metadata else None
        key = (font.family.strip().lower(), (owner or "").strip().lower())
        acc = groups.get(key)
        if acc is None:
            acc = _Accumulator(family=font.family)
            groups[key] = acc

        if acc.owner is None and owner:
            acc.owner = owner
        if acc.metadata is None and font.metadata is not None:
            acc.metadata = font.metadata

        acc.domains.add(_domain_of(font.source_page))
        acc.formats.add(font.font_format)
        acc.embeddings.add(font.embedding)
        acc.occurrences += 1
        acc.pages.add(font.source_page)
        acc.applied = acc.applied or font.applied

    result: list[AggregatedFont] = []
    for acc in groups.values():
        result.append(
            AggregatedFont(
                family=acc.family,
                family_group=base_family(acc.family),
                owner=acc.owner,
                domains=sorted(acc.domains),
                formats=sorted(acc.formats, key=lambda f: f.value),
                embeddings=sorted(acc.embeddings, key=lambda e: e.value),
                metadata=acc.metadata,
                occurrences=acc.occurrences,
                example_urls=sorted(acc.pages)[:5],
                page_count=len(acc.pages),
                applied=acc.applied,
                privacy=_classify_privacy(acc.embeddings),
            )
        )
    result.sort(key=lambda a: a.family.lower())
    return result


def validate_rules(rules: RulesConfig) -> list[str]:
    """Return human-readable problems with the classification config (empty if valid)."""

    errors: list[str] = []
    valid_embeddings = {e.value for e in EmbeddingMethod}
    valid_formats = {f.value for f in FontFormat}
    for cdn in rules.paid_cdns:
        if cdn not in valid_embeddings:
            errors.append(f"paid_cdns: unknown embedding method {cdn!r}")
    for fmt in rules.desktop_formats:
        if fmt not in valid_formats:
            errors.append(f"desktop_formats: unknown font format {fmt!r}")
    return errors


def _evidence_notes(agg: AggregatedFont, rules: RulesConfig) -> list[str]:
    notes: list[str] = []
    if clf.desktop_format_on_web(agg, rules.desktop_formats):
        notes.append("a desktop font format is served on the web")
    if clf.paid_cdn_delivery(agg, rules.paid_cdns):
        notes.append("served from a paid font CDN with no license on record")
    if clf.missing_license_string(agg):
        notes.append("the font file carries no license or copyright string")
    if clf.subset_signal(agg, rules.subset_max_glyphs):
        notes.append("the font looks subsetted (fewer glyphs than a full set)")
    if not agg.applied:
        notes.append("served but not applied to any text")
    return notes


def classify_license(
    agg: AggregatedFont, suppression: Suppression, rules: RulesConfig
) -> tuple[LicenseVerdict, str, list[str]]:
    """Deterministic license verdict + reason + evidence notes (first match wins)."""

    # 1. System/fallback fonts pose no license question.
    if not any(e is not EmbeddingMethod.SYSTEM for e in agg.embeddings):
        return LicenseVerdict.OK, "system or fallback font — no license needed", []

    # 2. A matching registry entry decides: covered -> OK; declared but lapsed or
    #    out of scope / over the domain limit -> VIOLATION. (Declaration precedes
    #    the open-evidence check: a font you declared and let lapse is a violation.)
    if suppression.entry is not None:
        if suppression.status is FindingStatus.RESOLVED:
            reason = f"covered by your license ({suppression.entry.license_type})"
            return LicenseVerdict.OK, reason, []
        reason = suppression.reason or "the declared license does not cover this use"
        return LicenseVerdict.VIOLATION, reason, []

    # 3. No registry cover: provably open -> OK.
    if clf.looks_open_licensed(agg, rules.open_license_patterns):
        return LicenseVerdict.OK, "openly licensed (license string in the font file)", []
    if clf.owner_is_free(agg, rules.free_owners):
        return LicenseVerdict.OK, "from a known free foundry", []
    if clf.family_is_open(agg, rules.open_families):
        return LicenseVerdict.OK, "openly licensed (known open family)", []

    # 4. No cover and not open: definite violations.
    if clf.embedding_forbidden(agg):
        return (
            LicenseVerdict.VIOLATION,
            "the font's embedding bits (OS/2 fsType) forbid web embedding",
            [],
        )
    if clf.family_is_paid_tier(agg, rules.paid_tier_families):
        return LicenseVerdict.VIOLATION, "a paid tier is served with no license on record", []
    if clf.self_host_prohibited(
        agg, rules.self_host_prohibited.owners, rules.self_host_prohibited.families
    ):
        return LicenseVerdict.VIOLATION, "self-hosting is not permitted for this font", []

    # 5. The honest default.
    return (
        LicenseVerdict.NEEDS_CHECK,
        "no license on record and not provably open",
        _evidence_notes(agg, rules),
    )


def _severity(finding: Finding) -> tuple[int, int, str]:
    return (
        _VERDICT_RANK[finding.license_verdict],
        _PRIVACY_RANK.get(finding.privacy, 1),
        finding.family.lower(),
    )


def evaluate(
    fonts: list[DetectedFont], rules: RulesConfig, registry: Registry, now: date
) -> list[Finding]:
    """Aggregate, then classify every detected font into a deterministic finding."""

    findings: list[Finding] = []
    for agg in aggregate(fonts):
        suppression = evaluate_suppression(agg, registry, now)
        verdict, reason, notes = classify_license(agg, suppression, rules)
        findings.append(
            Finding(
                family=agg.family,
                family_group=agg.family_group,
                owner=agg.owner,
                domains=agg.domains,
                formats=agg.formats,
                embeddings=agg.embeddings,
                metadata=agg.metadata,
                license_verdict=verdict,
                license_reason=reason,
                evidence_notes=notes,
                privacy=agg.privacy,
                registry_match=suppression.entry is not None,
                example_urls=agg.example_urls,
                page_count=agg.page_count,
                applied=agg.applied,
            )
        )

    findings.sort(key=_severity)
    return findings
