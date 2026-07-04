"""Diff two runs over findings that need action: new, resolved, and changed.

Monitoring only cares about what changed, so findings that need no action (license
OK and no privacy leak) are excluded. A finding's identity across runs is
(family, owner), case-insensitive.
"""

from __future__ import annotations

from fontsentry.models import (
    DiffResult,
    Finding,
    FindingDelta,
    LicenseVerdict,
    RunReport,
)

_Key = tuple[str, str]

# Severity order for sorting output (most-attention-worthy first).
_RANK = {LicenseVerdict.VIOLATION: 0, LicenseVerdict.NEEDS_CHECK: 1, LicenseVerdict.OK: 2}


def _key(finding: Finding) -> _Key:
    return (finding.family.strip().lower(), (finding.owner or "").strip().lower())


def _action_index(report: RunReport) -> dict[_Key, Finding]:
    return {_key(f): f for f in report.findings if f.needs_action}


def diff_runs(previous: RunReport, current: RunReport) -> DiffResult:
    """Compare a previous run to the current run."""

    old = _action_index(previous)
    new = _action_index(current)

    new_findings = [new[k] for k in new.keys() - old.keys()]
    resolved_findings = [old[k] for k in old.keys() - new.keys()]

    changed: list[FindingDelta] = []
    unchanged = 0
    for key in old.keys() & new.keys():
        before, after = old[key], new[key]
        if before.license_verdict != after.license_verdict or before.domains != after.domains:
            changed.append(
                FindingDelta(
                    family=after.family,
                    owner=after.owner,
                    old_verdict=before.license_verdict,
                    new_verdict=after.license_verdict,
                    old_domains=before.domains,
                    new_domains=after.domains,
                )
            )
        else:
            unchanged += 1

    new_findings.sort(key=lambda f: (_RANK[f.license_verdict], f.family.lower()))
    resolved_findings.sort(key=lambda f: f.family.lower())
    changed.sort(key=lambda d: (_RANK[d.new_verdict], d.family.lower()))

    return DiffResult(
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        changed=changed,
        unchanged_count=unchanged,
    )
