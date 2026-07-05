"""JSON report build/write/load, summary counts, and HTML rendering."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fontsentry.models import (
    DomainFont,
    DomainReport,
    EmbeddingMethod,
    Finding,
    FontFormat,
    LicenseVerdict,
    PrivacyClass,
)
from fontsentry.report import json_report
from fontsentry.report.csv_report import build_csv
from fontsentry.report.html_report import render_html

GENERATED = datetime(2026, 6, 30, 12, 0, 0)


def _finding(
    family: str,
    *,
    verdict: LicenseVerdict = LicenseVerdict.NEEDS_CHECK,
    privacy: PrivacyClass = PrivacyClass.SELF_HOSTED,
    owner: str = "Acme Type",
) -> Finding:
    return Finding(
        family=family,
        owner=owner,
        domains=["example.com"],
        formats=[FontFormat.TTF],
        embeddings=[EmbeddingMethod.SELF_HOSTED],
        license_verdict=verdict,
        license_reason="reason",
        privacy=privacy,
    )


def test_csv_neutralizes_formula_injection() -> None:
    import csv as _csv

    findings = [
        Finding(family="=1+1", owner="@evil", license_verdict=LicenseVerdict.VIOLATION),
        Finding(family="-2+3", owner="+cmd", license_verdict=LicenseVerdict.OK),
    ]
    report = json_report.build_report(findings, GENERATED)
    rows = list(_csv.reader(build_csv(report).splitlines()))
    body = rows[1:]
    assert body[0][0] == "'=1+1"
    assert body[0][2] == "'@evil"
    assert body[1][0] == "'-2+3"


def test_csv_preserves_and_quotes_special_chars() -> None:
    import csv as _csv

    f = Finding(family='Ac"me, Sans', owner="Acme", license_verdict=LicenseVerdict.OK)
    report = json_report.build_report([f], GENERATED)
    rows = list(_csv.reader(build_csv(report).splitlines()))
    assert rows[1][0] == 'Ac"me, Sans'  # round-trips through the CSV quoting intact


def test_load_run_tolerates_unknown_fields(tmp_path: Path) -> None:
    import json

    report = json_report.build_report([_finding("Atlas")], GENERATED)
    raw = json.loads(report.model_dump_json())
    raw["some_future_field"] = 123
    raw["findings"][0]["another_new_field"] = "x"
    path = tmp_path / "fontsentry-20260630T120000Z.report.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = json_report.load_run(path)
    assert loaded.findings[0].family == "Atlas"
    assert not hasattr(loaded, "some_future_field")


def test_build_summary_counts() -> None:
    findings = [
        _finding("A", verdict=LicenseVerdict.VIOLATION),
        _finding("B", verdict=LicenseVerdict.NEEDS_CHECK),
        _finding("C", verdict=LicenseVerdict.OK),
    ]
    summary = json_report.build_summary(findings)
    assert summary.total_findings == 3
    assert summary.needs_action == 2  # violation + needs_check (OK w/ self-hosted privacy = no)
    assert summary.by_verdict[LicenseVerdict.VIOLATION] == 1
    assert summary.by_verdict[LicenseVerdict.OK] == 1


def test_write_and_load_roundtrip(tmp_path: Path) -> None:
    report = json_report.build_report([_finding("A", verdict=LicenseVerdict.VIOLATION)], GENERATED)
    path = json_report.write_run(report, tmp_path)
    assert path.name == "fontsentry-20260630T120000Z.report.json"

    loaded = json_report.load_run(path)
    assert loaded.generated_at == GENERATED
    assert loaded.findings[0].family == "A"
    assert loaded.summary.needs_action == 1


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
    report_at("20260201T000000Z", ["Atlas", "Beacon"])

    m = json_report.first_seen_map(tmp_path)
    assert m[("example.com", "Atlas")] == datetime(2026, 1, 1, 0, 0, 0)
    assert m[("example.com", "Beacon")] == datetime(2026, 2, 1, 0, 0, 0)


def test_build_csv_has_header_and_rows() -> None:
    report = json_report.build_report(
        [
            _finding("A", verdict=LicenseVerdict.VIOLATION),
            _finding("B", verdict=LicenseVerdict.OK),
        ],
        GENERATED,
    )
    csv_text = build_csv(report)
    lines = csv_text.splitlines()
    assert lines[0].startswith("family,family_group,owner,license_verdict,license_reason,privacy")
    assert any(row.startswith("A,") for row in lines[1:])
    assert "violation" in csv_text


def test_render_html_contains_findings_and_disclaimer() -> None:
    report = json_report.build_report(
        [_finding("Atlas Grotesk Private", verdict=LicenseVerdict.VIOLATION)], GENERATED
    )
    html = render_html(report)
    assert "Atlas Grotesk Private" in html
    assert "not legal advice" in html
    assert "verdict-violation" in html


def test_render_html_escapes_untrusted_metadata() -> None:
    report = json_report.build_report(
        [_finding("<script>alert(1)</script>", verdict=LicenseVerdict.OK)], GENERATED
    )
    html = render_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
