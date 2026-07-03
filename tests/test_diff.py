"""Run-to-run diff over open findings: new, resolved, changed."""

from __future__ import annotations

from datetime import datetime

from fontsentry.models import Finding, FindingStatus, RiskBand, RunReport
from fontsentry.report.diff import diff_runs
from fontsentry.report.json_report import build_report


def _finding(
    family: str,
    *,
    score: int,
    domains: list[str],
    status: FindingStatus = FindingStatus.OPEN,
    owner: str = "Acme Type",
) -> Finding:
    return Finding(
        family=family,
        owner=owner,
        domains=domains,
        score=score,
        band=RiskBand.MEDIUM,
        status=status,
    )


def _report(findings: list[Finding]) -> RunReport:
    return build_report(findings, datetime(2026, 6, 30, 12, 0, 0))


def test_diff_identity_is_case_and_whitespace_insensitive() -> None:
    previous = _report([_finding("Atlas", score=50, domains=["a.com"], owner="Acme")])
    current = _report([_finding(" atlas ", score=70, domains=["a.com"], owner="ACME")])
    result = diff_runs(previous, current)
    # Same (family, owner) identity modulo case/whitespace -> changed, not new+resolved.
    assert result.new_findings == [] and result.resolved_findings == []
    assert [c.family for c in result.changed] == [" atlas "]


def test_diff_same_family_different_owner_are_distinct() -> None:
    previous = _report([_finding("Atlas", score=50, domains=["a.com"], owner="Foundry A")])
    current = _report([_finding("Atlas", score=50, domains=["a.com"], owner="Foundry B")])
    result = diff_runs(previous, current)
    assert [f.owner for f in result.new_findings] == ["Foundry B"]
    assert [f.owner for f in result.resolved_findings] == ["Foundry A"]


def test_diff_open_to_resolved_counts_as_resolved() -> None:
    # The "we bought a license" case: same finding, OPEN previously, RESOLVED now.
    previous = _report([_finding("Atlas", score=50, domains=["a.com"])])
    current = _report(
        [_finding("Atlas", score=50, domains=["a.com"], status=FindingStatus.RESOLVED)]
    )
    result = diff_runs(previous, current)
    assert [f.family for f in result.resolved_findings] == ["Atlas"]
    assert result.new_findings == []


def test_new_and_resolved_findings() -> None:
    previous = _report([_finding("Stays", score=50, domains=["a.com"])])
    current = _report(
        [
            _finding("Stays", score=50, domains=["a.com"]),
            _finding("Brand New", score=70, domains=["b.com"]),
        ]
    )
    result = diff_runs(previous, current)
    assert [f.family for f in result.new_findings] == ["Brand New"]
    assert result.resolved_findings == []
    assert result.unchanged_count == 1


def test_resolved_when_finding_disappears() -> None:
    previous = _report([_finding("Gone", score=50, domains=["a.com"])])
    current = _report([])
    result = diff_runs(previous, current)
    assert [f.family for f in result.resolved_findings] == ["Gone"]


def test_score_change_detected() -> None:
    previous = _report([_finding("Shift", score=40, domains=["a.com"])])
    current = _report([_finding("Shift", score=75, domains=["a.com"])])
    result = diff_runs(previous, current)
    assert len(result.changed) == 1
    assert result.changed[0].old_score == 40
    assert result.changed[0].new_score == 75


def test_domain_spread_change_detected() -> None:
    previous = _report([_finding("Spread", score=50, domains=["a.com"])])
    current = _report([_finding("Spread", score=50, domains=["a.com", "b.com"])])
    result = diff_runs(previous, current)
    assert len(result.changed) == 1
    assert result.changed[0].new_domains == ["a.com", "b.com"]


def test_suppressed_findings_ignored_in_diff() -> None:
    previous = _report([])
    current = _report(
        [_finding("Licensed", score=0, domains=["a.com"], status=FindingStatus.RESOLVED)]
    )
    result = diff_runs(previous, current)
    assert not result.has_changes
