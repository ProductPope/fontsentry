"""Match aggregated fonts against the owned-license registry and decide suppression.

A finding is suppressed (status RESOLVED, no alert) only when a matching license
genuinely covers it: same owner + family, the license is not expired, every
observed host is covered by an allowed domain (a license for "example.com" covers
its subdomains like "www.example.com"; "*" covers everything), and the number of
distinct licensed domains in use is within max_domains. Anything short of that
surfaces as an open finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

from fontsentry.models import (
    AggregatedFont,
    FindingStatus,
    Registry,
    RegistryEntry,
)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def find_entry(registry: Registry, owner: str | None, family: str) -> RegistryEntry | None:
    """Return the registry entry matching owner + family (case-insensitive), if any."""

    for entry in registry.entries:
        if _norm(entry.owner) == _norm(owner) and _norm(entry.family) == _norm(family):
            return entry
    return None


def is_expired(entry: RegistryEntry, now: date) -> bool:
    return entry.valid_until is not None and entry.valid_until < now


def _covers(host: str, allowed: str) -> bool:
    # A licensed domain covers itself and its subdomains (dot-bounded), matching
    # how licenses are granted in practice: "example.com" covers "www.example.com".
    return host == allowed or host.endswith("." + allowed)


def _covering_domain(host: str, allowed: set[str]) -> str:
    # The licensed domain a host falls under (for counting distinct sites toward
    # max_domains); the host itself if it isn't covered by any.
    return next((d for d in allowed if d != "*" and _covers(host, d)), host)


@dataclass(frozen=True)
class Suppression:
    status: FindingStatus
    entry: RegistryEntry | None
    reason: str | None


def evaluate_suppression(agg: AggregatedFont, registry: Registry, now: date) -> Suppression:
    """Decide whether an aggregated font is covered by a license."""

    entry = find_entry(registry, agg.owner, agg.family)
    if entry is None:
        return Suppression(FindingStatus.OPEN, None, "no matching license in registry")

    if is_expired(entry, now):
        return Suppression(FindingStatus.OPEN, entry, "matching license has expired")

    allowed = {_norm(d) for d in entry.allowed_domains}
    observed = {_norm(d) for d in agg.domains}
    wildcard = "*" in allowed
    # "*" is a wildcard: the license covers any domain (unlimited scope).
    if not wildcard:
        uncovered = sorted(h for h in observed if not any(_covers(h, d) for d in allowed))
        if uncovered:
            return Suppression(
                FindingStatus.OPEN,
                entry,
                f"domains not covered by license: {', '.join(uncovered)}",
            )

    # Count distinct licensed domains in use (subdomains of one allowed domain
    # count once), not raw hostnames, so www + apex under one license == 1 domain.
    # A wildcard license has no domain list to fold under, so only the unambiguous
    # www+apex pair folds there (deeper subdomain folding would need a public-
    # suffix list to avoid miscounting the likes of example.co.uk).
    effective = (
        {h.removeprefix("www.") for h in observed}
        if wildcard
        else {_covering_domain(h, allowed) for h in observed}
    )
    if entry.max_domains is not None and len(effective) > entry.max_domains:
        return Suppression(
            FindingStatus.OPEN,
            entry,
            f"domain count {len(effective)} exceeds license max_domains {entry.max_domains}",
        )

    return Suppression(FindingStatus.RESOLVED, entry, "covered by a valid license")


def validate_registry(registry: Registry, proofs_dir: Path) -> list[str]:
    """Return problems with the registry: missing proof/invoice files and
    duplicate (owner, family) entries."""

    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in registry.entries:
        label = f"{entry.owner} / {entry.family}"
        # Matching takes the FIRST (owner, family) hit, so a renewal appended
        # below an expired entry silently loses — the verdict would depend on
        # file order. Duplicates are therefore a validation error, not a style nit.
        key = _entry_key(entry)
        if key in seen:
            errors.append(
                f"{label}: duplicate entry — only the first match is used; "
                "edit the existing entry instead of appending (e.g. for a renewal)"
            )
        seen.add(key)
        for kind, rel in (("proof", entry.proof_path), ("invoice", entry.invoice_path)):
            if rel is None:
                continue
            if not (proofs_dir / rel).exists():
                errors.append(f"{label}: {kind} file not found: {proofs_dir / rel}")
    return errors


def _entry_key(entry: RegistryEntry) -> tuple[str, str]:
    return (entry.owner.strip().lower(), entry.family.strip().lower())


class MergeResult(NamedTuple):
    registry: Registry
    added: int
    replaced: int


def merge_registries(base: Registry, incoming: Registry) -> MergeResult:
    """Upsert ``incoming`` entries into ``base`` by (owner, family), case-insensitively.

    Incoming wins on a matching (owner, family); non-matching existing entries are
    kept and nothing is deleted (a safe import: it never silently drops licenses).
    Base order is preserved; genuinely new entries are appended in incoming order.
    Replacements are counted so the caller can tell the operator: an incoming entry
    can be *less* strict than the one it overwrites (e.g. no expiry, no domain
    scope), and that must not happen invisibly.
    """

    index = {_entry_key(entry): position for position, entry in enumerate(base.entries)}
    merged = list(base.entries)
    added = replaced = 0
    for entry in incoming.entries:
        key = _entry_key(entry)
        existing = index.get(key)
        if existing is None:
            index[key] = len(merged)
            merged.append(entry)
            added += 1
        else:
            if merged[existing] != entry:
                replaced += 1
            merged[existing] = entry
    return MergeResult(Registry(entries=merged), added, replaced)
