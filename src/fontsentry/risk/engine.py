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
    example_url: str | None = None


def _domain_of(url: str) -> str:
    return urlparse(url).hostname or url


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
        if acc.example_url is None:
            acc.example_url = font.source_page

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
                example_url=acc.example_url,
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
                example_url=agg.example_url,
            )
        )

    findings.sort(key=lambda f: (-f.score, f.family.lower()))
    return findings
