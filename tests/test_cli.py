"""CLI surface tests via Typer's CliRunner. Demo path keeps everything offline."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fontsentry.cli import app

runner = CliRunner()


def test_scan_demo_writes_reports(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", "--demo", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    jsons = list(tmp_path.glob("*.report.json"))
    htmls = list(tmp_path.glob("*.report.html"))
    assert len(jsons) == 1
    assert len(htmls) == 1


def test_scan_demo_csv_and_max_pages(tmp_path: Path) -> None:
    # CLI parity with the API: --csv writes a findings CSV; --max-pages is accepted.
    result = runner.invoke(
        app, ["scan", "--demo", "--output", str(tmp_path), "--csv", "--max-pages", "3"]
    )
    assert result.exit_code == 0, result.output
    csvs = list(tmp_path.glob("*.csv"))
    assert len(csvs) == 1
    assert (
        csvs[0].read_text(encoding="utf-8").splitlines()[0].startswith("family,family_group,owner")
    )


def test_report_rerenders_html(tmp_path: Path) -> None:
    runner.invoke(app, ["scan", "--demo", "--output", str(tmp_path)])
    run_json = next(tmp_path.glob("*.report.json"))
    out = tmp_path / "rerender.html"
    result = runner.invoke(app, ["report", str(run_json), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_rules_validate_ok(repo_root: Path) -> None:
    result = runner.invoke(
        app, ["rules", "validate", "--file", str(repo_root / "config" / "rules.example.yaml")]
    )
    assert result.exit_code == 0
    assert "rules OK" in result.output


def test_registry_validate_ok(repo_root: Path) -> None:
    result = runner.invoke(
        app,
        ["registry", "validate", "--file", str(repo_root / "demo" / "registry" / "licenses.yaml")],
    )
    assert result.exit_code == 0
    assert "registry OK" in result.output


def test_diff_two_runs(tmp_path: Path, repo_root: Path) -> None:
    # Two hand-written runs: one new open finding appears in the second.
    older = tmp_path / "fontsentry-20260101T000000Z.report.json"
    newer = tmp_path / "fontsentry-20260201T000000Z.report.json"
    older.write_text(
        '{"schema_version":1,"generated_at":"2026-01-01T00:00:00Z",'
        '"summary":{"total_findings":0,"open_findings":0,"resolved_findings":0,"by_band":{}},'
        '"findings":[]}',
        encoding="utf-8",
    )
    newer.write_text(
        '{"schema_version":1,"generated_at":"2026-02-01T00:00:00Z",'
        '"summary":{"total_findings":1,"open_findings":1,"resolved_findings":0,"by_band":{}},'
        '"findings":[{"family":"New Font","owner":"Acme","domains":["a.com"],'
        '"formats":["ttf"],"embeddings":["self_hosted"],"score":70,"band":"high",'
        '"status":"open","triggered_rules":[],"registry_match":false}]}',
        encoding="utf-8",
    )
    result = runner.invoke(app, ["diff", str(older), str(newer)])
    assert "NEW" in result.output
    assert "New Font" in result.output
    assert result.exit_code == 1  # new findings -> non-zero for CI gating
