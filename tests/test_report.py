"""JSON report build/write/load, summary counts, and HTML rendering."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fontsentry.models import (
    EmbeddingMethod,
    Finding,
    FindingStatus,
    FontFormat,
    RiskBand,
)
from fontsentry.report import json_report
from fontsentry.report.html_report import render_html

GENERATED = datetime(2026, 6, 30, 12, 0, 0)


def _finding(
    family: str,
    *,
    score: int,
    band: RiskBand,
    status: FindingStatus = FindingStatus.OPEN,
    owner: str = "Acme Type",
) -> Finding:
    return Finding(
        family=family,
        owner=owner,
        domains=["example.com"],
        formats=[FontFormat.TTF],
        embeddings=[EmbeddingMethod.SELF_HOSTED],
        score=score,
        band=band,
        status=status,
    )


def test_build_summary_counts() -> None:
    findings = [
        _finding("A", score=80, band=RiskBand.HIGH),
        _finding("B", score=40, band=RiskBand.MEDIUM),
        _finding("C", score=10, band=RiskBand.LOW, status=FindingStatus.RESOLVED),
    ]
    summary = json_report.build_summary(findings)
    assert summary.total_findings == 3
    assert summary.open_findings == 2
    assert summary.resolved_findings == 1
    assert summary.by_band[RiskBand.HIGH] == 1
    assert summary.by_band[RiskBand.LOW] == 1


def test_write_and_load_roundtrip(tmp_path: Path) -> None:
    report = json_report.build_report([_finding("A", score=80, band=RiskBand.HIGH)], GENERATED)
    path = json_report.write_run(report, tmp_path)
    assert path.name == "fontsentry-20260630T120000Z.report.json"

    loaded = json_report.load_run(path)
    assert loaded.generated_at == GENERATED
    assert loaded.findings[0].family == "A"
    assert loaded.summary.open_findings == 1


def test_latest_runs_orders_newest_first(tmp_path: Path) -> None:
    for ts in ("20260101T000000Z", "20260301T000000Z", "20260201T000000Z"):
        (tmp_path / f"fontsentry-{ts}.report.json").write_text("{}", encoding="utf-8")
    latest = json_report.latest_runs(tmp_path, limit=2)
    assert [p.name for p in latest] == [
        "fontsentry-20260301T000000Z.report.json",
        "fontsentry-20260201T000000Z.report.json",
    ]


def test_render_html_contains_findings_and_disclaimer() -> None:
    report = json_report.build_report(
        [_finding("Atlas Grotesk Private", score=82, band=RiskBand.HIGH)], GENERATED
    )
    html = render_html(report)
    assert "Atlas Grotesk Private" in html
    assert "not legal advice" in html
    assert "band-high" in html


def test_render_html_escapes_untrusted_metadata() -> None:
    report = json_report.build_report(
        [_finding("<script>alert(1)</script>", score=10, band=RiskBand.LOW)], GENERATED
    )
    html = render_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
