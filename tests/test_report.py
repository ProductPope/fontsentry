"""JSON report build/write/load, summary counts, and HTML rendering."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fontsentry.models import (
    DomainFont,
    DomainReport,
    EmbeddingMethod,
    Finding,
    FindingStatus,
    FontFormat,
    RiskBand,
)
from fontsentry.report import json_report
from fontsentry.report.csv_report import build_csv
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


def test_csv_neutralizes_formula_injection() -> None:
    import csv as _csv

    findings = [
        Finding(family="=1+1", owner="@evil", score=50, band=RiskBand.MEDIUM),
        Finding(family="-2+3", owner="+cmd", score=10, band=RiskBand.LOW),
    ]
    report = json_report.build_report(findings, GENERATED)
    rows = list(_csv.reader(build_csv(report).splitlines()))
    body = rows[1:]
    # Every dangerous cell is prefixed with an apostrophe so spreadsheets treat
    # it as text, not a formula.
    assert body[0][0] == "'=1+1"
    assert body[0][2] == "'@evil"
    assert body[1][0] == "'-2+3"


def test_csv_preserves_and_quotes_special_chars() -> None:
    import csv as _csv

    f = Finding(family='Ac"me, Sans', owner="Acme", score=5, band=RiskBand.LOW)
    report = json_report.build_report([f], GENERATED)
    rows = list(_csv.reader(build_csv(report).splitlines()))
    assert rows[1][0] == 'Ac"me, Sans'  # round-trips through the CSV quoting intact


def test_load_run_tolerates_unknown_fields(tmp_path: Path) -> None:
    # Forward/back-compat: a report written by another tool version carrying an
    # unknown field (top-level and nested) must still load, not hard-fail.
    import json

    report = json_report.build_report(
        [_finding("Atlas", score=50, band=RiskBand.MEDIUM)], GENERATED
    )
    raw = json.loads(report.model_dump_json())
    raw["some_future_field"] = 123
    raw["findings"][0]["another_new_field"] = "x"
    path = tmp_path / "fontsentry-20260630T120000Z.report.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = json_report.load_run(path)
    assert loaded.findings[0].family == "Atlas"
    assert not hasattr(loaded, "some_future_field")  # unknown field dropped, not kept


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


def test_first_seen_map_earliest_wins(tmp_path: Path) -> None:
    def report_at(ts: str, families: list[str]) -> None:
        report = json_report.build_report(
            [],
            datetime.strptime(ts, "%Y%m%dT%H%M%SZ"),
            domains=[
                DomainReport(domain="example.com", fonts=[DomainFont(family=f) for f in families])
            ],
        )
        json_report.write_run(report, tmp_path)

    report_at("20260101T000000Z", ["Atlas"])
    report_at("20260201T000000Z", ["Atlas", "Beacon"])  # Atlas seen earlier; Beacon is new

    m = json_report.first_seen_map(tmp_path)
    assert m[("example.com", "Atlas")] == datetime(2026, 1, 1, 0, 0, 0)
    assert m[("example.com", "Beacon")] == datetime(2026, 2, 1, 0, 0, 0)


def test_build_csv_has_header_and_rows() -> None:
    report = json_report.build_report(
        [
            _finding("A", score=80, band=RiskBand.HIGH),
            _finding("B", score=10, band=RiskBand.LOW, status=FindingStatus.RESOLVED),
        ],
        GENERATED,
    )
    csv_text = build_csv(report)
    lines = csv_text.splitlines()
    assert lines[0].startswith("family,family_group,owner,band,score,status,privacy,applied")
    assert any(row.startswith("A,") for row in lines[1:])
    assert "high" in csv_text and "resolved" in csv_text


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
