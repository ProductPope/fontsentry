"""Diff two runs over open (alertable) findings: new, resolved, and changed.

Monitoring only cares about what changed, so suppressed (RESOLVED) findings are
excluded. A finding's identity across runs is (family, foundry), case-insensitive.
"""

from __future__ import annotations

from fontsentry.models import (
    DiffResult,
    Finding,
    FindingDelta,
    FindingStatus,
    RunReport,
)

_Key = tuple[str, str]


def _key(finding: Finding) -> _Key:
    return (finding.family.strip().lower(), (finding.foundry or "").strip().lower())


def _open_index(report: RunReport) -> dict[_Key, Finding]:
    return {_key(f): f for f in report.findings if f.status is FindingStatus.OPEN}


def diff_runs(previous: RunReport, current: RunReport) -> DiffResult:
    """Compare a previous run to the current run."""

    old = _open_index(previous)
    new = _open_index(current)

    new_findings = [new[k] for k in new.keys() - old.keys()]
    resolved_findings = [old[k] for k in old.keys() - new.keys()]

    changed: list[FindingDelta] = []
    unchanged = 0
    for key in old.keys() & new.keys():
        before, after = old[key], new[key]
        if before.score != after.score or before.domains != after.domains:
            changed.append(
                FindingDelta(
                    family=after.family,
                    foundry=after.foundry,
                    old_score=before.score,
                    new_score=after.score,
                    old_domains=before.domains,
                    new_domains=after.domains,
                )
            )
        else:
            unchanged += 1

    new_findings.sort(key=lambda f: (-f.score, f.family.lower()))
    resolved_findings.sort(key=lambda f: f.family.lower())
    changed.sort(key=lambda d: (-d.new_score, d.family.lower()))

    return DiffResult(
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        changed=changed,
        unchanged_count=unchanged,
    )
