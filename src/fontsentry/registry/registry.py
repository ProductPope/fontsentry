"""Match aggregated fonts against the owned-license registry and decide suppression.

A finding is suppressed (status RESOLVED, no alert) only when a matching license
genuinely covers it: same owner + family, the license is not expired, every
observed domain is allowed (or allowed_domains contains the "*" wildcard), and
the global domain count is within max_domains. Anything short of that surfaces
as an open finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
    # "*" is a wildcard: the license covers any domain (unlimited scope).
    if "*" not in allowed and not observed <= allowed:
        uncovered = sorted(observed - allowed)
        return Suppression(
            FindingStatus.OPEN, entry, f"domains not covered by license: {', '.join(uncovered)}"
        )

    if entry.max_domains is not None and agg.domain_count > entry.max_domains:
        return Suppression(
            FindingStatus.OPEN,
            entry,
            f"domain count {agg.domain_count} exceeds license max_domains {entry.max_domains}",
        )

    return Suppression(FindingStatus.RESOLVED, entry, "covered by a valid license")


def validate_registry(registry: Registry, proofs_dir: Path) -> list[str]:
    """Return problems with the registry: referenced proof/invoice files that are missing."""

    errors: list[str] = []
    for entry in registry.entries:
        label = f"{entry.owner} / {entry.family}"
        for kind, rel in (("proof", entry.proof_path), ("invoice", entry.invoice_path)):
            if rel is None:
                continue
            if not (proofs_dir / rel).exists():
                errors.append(f"{label}: {kind} file not found: {proofs_dir / rel}")
    return errors
