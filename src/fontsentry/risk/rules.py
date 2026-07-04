"""Classification helpers: the auditable checks the deterministic engine composes.

Each function is a pure predicate over an aggregated font plus classification data
from ``rules.yaml`` (ADR 0003). No weights, no scoring — the engine wires these
into a fixed decision table.
"""

from __future__ import annotations

from fontsentry.models import AggregatedFont, EmbeddingMethod, FamilySpec, FontFormat


def _license_text(agg: AggregatedFont) -> str:
    meta = agg.metadata
    if meta is None:
        return ""
    parts = [meta.license_description, meta.copyright, meta.license_url]
    return " ".join(p for p in parts if p).lower()


def looks_open_licensed(agg: AggregatedFont, patterns: list[str]) -> bool:
    text = _license_text(agg)
    return any(str(p).lower() in text for p in patterns)


def owner_is_free(agg: AggregatedFont, free_owners: list[str]) -> bool:
    free = {str(f).strip().lower() for f in free_owners}
    return (agg.owner or "").strip().lower() in free


def _family_matches(family: str, spec: FamilySpec) -> bool:
    inc = [s.strip().lower() for s in spec.contains_all]
    exc = [s.strip().lower() for s in spec.excludes]
    if not inc:
        return False
    return all(s in family for s in inc) and not any(s in family for s in exc)


def family_is_open(agg: AggregatedFont, open_families: list[FamilySpec]) -> bool:
    # Recognize openly-licensed families whose name-table license string is stripped
    # (e.g. Font Awesome Free/Brands). `excludes` keeps paid tiers out.
    family = agg.family.strip().lower()
    return any(_family_matches(family, spec) for spec in open_families)


def family_is_paid_tier(agg: AggregatedFont, paid_tier_families: list[FamilySpec]) -> bool:
    # A paid tier announced by the family name itself (e.g. "Font Awesome ... Pro").
    family = agg.family.strip().lower()
    return any(_family_matches(family, spec) for spec in paid_tier_families)


def self_host_prohibited(agg: AggregatedFont, owners: list[str], families: list[str]) -> bool:
    if EmbeddingMethod.SELF_HOSTED not in agg.embeddings:
        return False
    owner_set = {o.strip().lower() for o in owners}
    family_set = {f.strip().lower() for f in families}
    owner_hit = (agg.owner or "").strip().lower() in owner_set
    family_hit = agg.family.strip().lower() in family_set
    return owner_hit or family_hit


def desktop_format_on_web(agg: AggregatedFont, desktop_formats: list[str]) -> bool:
    targets = {str(f).lower() for f in desktop_formats}
    present = {f.value for f in agg.formats}
    served_on_web = any(e is not EmbeddingMethod.SYSTEM for e in agg.embeddings)
    return bool(targets & present) and served_on_web


def paid_cdn_delivery(agg: AggregatedFont, paid_cdns: list[str]) -> bool:
    wanted: set[EmbeddingMethod] = set()
    for name in paid_cdns:
        try:
            wanted.add(EmbeddingMethod(str(name)))
        except ValueError:
            continue
    return any(e in wanted for e in agg.embeddings)


def missing_license_string(agg: AggregatedFont) -> bool:
    meta = agg.metadata
    if meta is None:
        return False  # no file read -> no evidence either way
    return not meta.license_description and not meta.copyright


def subset_signal(agg: AggregatedFont, max_glyphs: int) -> bool:
    meta = agg.metadata
    if meta is None or meta.num_glyphs is None:
        return False
    has_web_format = any(f in (FontFormat.WOFF2, FontFormat.WOFF) for f in agg.formats)
    return has_web_format and meta.num_glyphs < max_glyphs
