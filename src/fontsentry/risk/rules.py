"""Rule predicates: the fixed, auditable vocabulary the rule engine can use.

Each predicate name maps a `when.type` in rules.yaml to a function. The function
reads its parameters from the rule (pure data), so new rules are added by editing
YAML; only a genuinely new *kind* of check needs code here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fontsentry.models import AggregatedFont, EmbeddingMethod, FontFormat, RegistryEntry
from fontsentry.registry.registry import is_expired

_DEFAULT_SUBSET_MAX_GLYPHS = 256


@dataclass(frozen=True)
class PredicateContext:
    agg: AggregatedFont
    entry: RegistryEntry | None
    now: date
    params: dict[str, Any]


Predicate = Callable[[PredicateContext], bool]


def _embeddings_excluding_system(agg: AggregatedFont) -> bool:
    return any(e is not EmbeddingMethod.SYSTEM for e in agg.embeddings)


def _license_text(ctx: PredicateContext) -> str:
    meta = ctx.agg.metadata
    if meta is None:
        return ""
    parts = [meta.license_description, meta.copyright, meta.license_url]
    return " ".join(p for p in parts if p).lower()


def _looks_open_licensed(ctx: PredicateContext) -> bool:
    patterns = [str(p).lower() for p in ctx.params.get("open_license_patterns", [])]
    text = _license_text(ctx)
    return any(pat in text for pat in patterns)


def _owner_is_free(ctx: PredicateContext) -> bool:
    free = {str(f).strip().lower() for f in ctx.params.get("free_owners", [])}
    return (ctx.agg.owner or "").strip().lower() in free


def _family_matches(family: str, contains_all: Any, excludes: Any) -> bool:
    """True when `family` contains every substring in `contains_all` and none in
    `excludes`. Matching is case-insensitive substring; an empty `contains_all`
    never matches (a spec must positively name what it targets)."""
    inc = [str(s).strip().lower() for s in contains_all or []]
    exc = [str(s).strip().lower() for s in excludes or []]
    if not inc:
        return False
    return all(s in family for s in inc) and not any(s in family for s in exc)


def _family_is_open(ctx: PredicateContext) -> bool:
    # A font can be recognized as openly licensed by its family name alone, for
    # families whose name-table license string is stripped (e.g. Font Awesome
    # Free/Brands carry no OFL string but are OFL-licensed). Each spec includes
    # `excludes` so paid tiers of the same family (e.g. "... Pro") are NOT caught.
    family = ctx.agg.family.strip().lower()
    for spec in ctx.params.get("open_families", []):
        if _family_matches(family, spec.get("contains_all", []), spec.get("excludes", [])):
            return True
    return False


def format_on_web(ctx: PredicateContext) -> bool:
    targets = {str(f).lower() for f in ctx.params.get("formats", [])}
    present = {f.value for f in ctx.agg.formats}
    return bool(targets & present) and _embeddings_excluding_system(ctx.agg)


def commercial_unregistered(ctx: PredicateContext) -> bool:
    # Needs evidence: we only assert "commercial" when we have name-table metadata.
    if ctx.entry is not None or ctx.agg.metadata is None:
        return False
    return not _looks_open_licensed(ctx) and not _owner_is_free(ctx) and not _family_is_open(ctx)


def max_domains_exceeded(ctx: PredicateContext) -> bool:
    entry = ctx.entry
    return (
        entry is not None
        and entry.max_domains is not None
        and (ctx.agg.domain_count > entry.max_domains)
    )


def self_host_prohibited(ctx: PredicateContext) -> bool:
    if EmbeddingMethod.SELF_HOSTED not in ctx.agg.embeddings:
        return False
    owners = {str(f).strip().lower() for f in ctx.params.get("owners", [])}
    families = {str(f).strip().lower() for f in ctx.params.get("families", [])}
    owner = (ctx.agg.owner or "").strip().lower()
    family = ctx.agg.family.strip().lower()
    return owner in owners or family in families


def paid_cdn_unregistered(ctx: PredicateContext) -> bool:
    if ctx.entry is not None:
        return False
    wanted: set[EmbeddingMethod] = set()
    for name in ctx.params.get("cdns", []):
        try:
            wanted.add(EmbeddingMethod(str(name)))
        except ValueError:
            continue
    return any(e in wanted for e in ctx.agg.embeddings)


def missing_name_field(ctx: PredicateContext) -> bool:
    meta = ctx.agg.metadata
    if meta is None:
        return False  # no file read -> no evidence either way
    field_map = {
        "copyright": meta.copyright,
        "license": meta.license_description,
        "license_url": meta.license_url,
        "owner": meta.owner,
        "designer": meta.designer,
        "unique_id": meta.unique_id,
    }
    for field in ctx.params.get("fields", []):
        # Only known field names count; an unknown/misspelled name is ignored
        # rather than treated as "missing" (which would fire the rule spuriously).
        key = str(field)
        if key in field_map and not field_map[key]:
            return True
    return False


def license_expired(ctx: PredicateContext) -> bool:
    return ctx.entry is not None and is_expired(ctx.entry, ctx.now)


def family_name_matches(ctx: PredicateContext) -> bool:
    # A positive risk signal carried by the family name itself — e.g. a paid tier
    # like "Font Awesome ... Pro". `contains_all` must all be present; `excludes`
    # (optional) must all be absent.
    return _family_matches(
        ctx.agg.family.strip().lower(),
        ctx.params.get("contains_all", []),
        ctx.params.get("excludes", []),
    )


def subset_signal(ctx: PredicateContext) -> bool:
    meta = ctx.agg.metadata
    if meta is None or meta.num_glyphs is None:
        return False
    threshold = int(ctx.params.get("max_glyphs", _DEFAULT_SUBSET_MAX_GLYPHS))
    has_web_format = any(f in (FontFormat.WOFF2, FontFormat.WOFF) for f in ctx.agg.formats)
    return has_web_format and meta.num_glyphs < threshold


PREDICATES: dict[str, Predicate] = {
    "format_on_web": format_on_web,
    "commercial_unregistered": commercial_unregistered,
    "max_domains_exceeded": max_domains_exceeded,
    "self_host_prohibited": self_host_prohibited,
    "paid_cdn_unregistered": paid_cdn_unregistered,
    "missing_name_field": missing_name_field,
    "license_expired": license_expired,
    "family_name_matches": family_name_matches,
    "subset_signal": subset_signal,
}


def known_predicate_types() -> set[str]:
    return set(PREDICATES)
