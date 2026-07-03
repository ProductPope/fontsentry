"""The risk engine: aggregate detected fonts, then score them rule by rule.

Aggregation runs over the *whole* crawl before scoring, so cross-domain rules
(e.g. max_domains) see every domain a font appears on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from fontsentry.models import (
    AggregatedFont,
    DetectedFont,
    EmbeddingMethod,
    Finding,
    FontFormat,
    FontMetadata,
    PrivacyClass,
    Registry,
    RegistryEntry,
    RiskBand,
    RulesConfig,
    TriggeredRule,
)
from fontsentry.registry.registry import evaluate_suppression
from fontsentry.risk.rules import PREDICATES, PredicateContext, known_predicate_types


class EngineError(Exception):
    """Raised when a rule references an unknown predicate type."""


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

    groups: dict[str, _Accumulator] = {}
    for font in fonts:
        key = font.family.strip().lower()
        acc = groups.get(key)
        if acc is None:
            acc = _Accumulator(family=font.family)
            groups[key] = acc

        owner = font.metadata.owner if font.metadata else None
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


def band_for(score: int, rules: RulesConfig) -> RiskBand:
    bands = rules.scoring.bands
    if score >= bands.high:
        return RiskBand.HIGH
    if score >= bands.medium:
        return RiskBand.MEDIUM
    return RiskBand.LOW


def validate_rules(rules: RulesConfig) -> list[str]:
    """Return a list of human-readable problems with the rule set (empty if valid)."""

    known = known_predicate_types()
    errors: list[str] = []
    for rule in rules.rules:
        if rule.when.type not in known:
            errors.append(
                f"rule {rule.id!r}: unknown condition type {rule.when.type!r} "
                f"(known: {', '.join(sorted(known))})"
            )
    return errors


def _score_font(
    agg: AggregatedFont, rules: RulesConfig, entry: RegistryEntry | None, now: date
) -> tuple[list[TriggeredRule], int, RiskBand]:
    raw = 0.0
    triggered: list[TriggeredRule] = []
    for rule in rules.rules:
        predicate = PREDICATES.get(rule.when.type)
        if predicate is None:
            raise EngineError(f"rule {rule.id!r}: unknown condition type {rule.when.type!r}")
        ctx = PredicateContext(agg=agg, entry=entry, now=now, params=rule.when.params)
        if predicate(ctx):
            points = rule.weight * rule.confidence
            raw += points
            triggered.append(
                TriggeredRule(
                    id=rule.id,
                    description=rule.description,
                    weight=rule.weight,
                    confidence=rule.confidence,
                    points=round(points, 2),
                )
            )

    score = min(100, round(100 * raw / rules.scoring.max_raw))
    return triggered, score, band_for(score, rules)


def evaluate(
    fonts: list[DetectedFont], rules: RulesConfig, registry: Registry, now: date
) -> list[Finding]:
    """Aggregate, suppress, and score every detected font into findings."""

    findings: list[Finding] = []
    for agg in aggregate(fonts):
        suppression = evaluate_suppression(agg, registry, now)
        triggered, score, band = _score_font(agg, rules, suppression.entry, now)
        # A font served via @font-face but not applied to any text is a weaker
        # signal (the file is hosted, but nothing renders in it): halve the score.
        if not agg.applied:
            score = round(score * 0.5)
            band = band_for(score, rules)
        findings.append(
            Finding(
                family=agg.family,
                owner=agg.owner,
                domains=agg.domains,
                formats=agg.formats,
                embeddings=agg.embeddings,
                metadata=agg.metadata,
                score=score,
                band=band,
                status=suppression.status,
                triggered_rules=triggered,
                registry_match=suppression.entry is not None,
                suppression_reason=suppression.reason,
                example_urls=agg.example_urls,
                page_count=agg.page_count,
                applied=agg.applied,
                privacy=agg.privacy,
            )
        )

    findings.sort(key=lambda f: (-f.score, f.family.lower()))
    return findings
