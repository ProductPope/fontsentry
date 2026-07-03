"""Typer CLI entry point.

This layer stays thin: it parses arguments, loads config, and calls into the
crawl / detect / risk / registry / report packages. No scoring or crawling logic
lives here.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from fontsentry import config, demo, scan
from fontsentry.models import DiffResult, Registry, RunReport
from fontsentry.registry.registry import validate_registry
from fontsentry.report.csv_report import build_csv
from fontsentry.report.diff import diff_runs
from fontsentry.report.html_report import write_html
from fontsentry.report.json_report import latest_runs, load_run
from fontsentry.risk.engine import validate_rules

app = typer.Typer(
    name="fontsentry",
    help="Audit and monitor web fonts for license-violation risk.",
    no_args_is_help=True,
    add_completion=False,
)
registry_app = typer.Typer(help="License-registry commands.", no_args_is_help=True)
rules_app = typer.Typer(help="Rule-file commands.", no_args_is_help=True)
app.add_typer(registry_app, name="registry")
app.add_typer(rules_app, name="rules")

console = Console()
err_console = Console(stderr=True)


@app.callback()
def main() -> None:
    """FontSentry CLI. The risk score is a heuristic estimate, not legal advice."""


def _print_summary(report: RunReport) -> None:
    s = report.summary
    console.print(
        f"[bold]{s.total_findings}[/] findings · "
        f"[red]{s.open_findings} open[/] · {s.resolved_findings} resolved"
    )
    table = Table(show_header=True, header_style="bold")
    for col in ("Font", "Owner", "Embedding", "Format", "Domains", "Score", "Band", "Status"):
        table.add_column(col)
    band_color = {"low": "green", "medium": "yellow", "high": "red"}
    for f in report.findings:
        table.add_row(
            f.family,
            f.owner or "—",
            ", ".join(e.value for e in f.embeddings) or "—",
            ", ".join(fmt.value for fmt in f.formats) or "—",
            str(f.domain_count),
            str(f.score),
            f"[{band_color[f.band.value]}]{f.band.value}[/]",
            f.status.value,
        )
    console.print(table)


@app.command("scan")
def scan_cmd(
    config_dir: Path = typer.Option(Path("config"), "--config-dir", help="Config directory."),
    registry_dir: Path = typer.Option(Path("registry"), "--registry-dir", help="Registry dir."),
    output: Path | None = typer.Option(None, "--output", help="Reports output directory."),
    demo_mode: bool = typer.Option(False, "--demo", help="Run the offline demo dataset."),
    discover_subdomains: bool = typer.Option(
        False,
        "--discover-subdomains",
        help="Also find public subdomains via Certificate Transparency (real mode only).",
    ),
    max_pages: int | None = typer.Option(
        None, "--max-pages", min=1, help="Override the per-host page cap for this scan."
    ),
    csv_out: bool = typer.Option(False, "--csv", help="Also write a CSV of the findings."),
) -> None:
    """Crawl, detect, score, and write JSON + HTML reports."""

    now = datetime.now(UTC).replace(microsecond=0)

    if demo_mode:
        settings = demo.demo_settings()
        rules = config.load_rules(config.resolve_config_path(config_dir, "rules"))
        registry = config.load_registry(demo.demo_registry_path())
        targets = demo.demo_targets()
        client = demo.demo_client()
    else:
        settings = config.load_settings(config.resolve_config_path(config_dir, "settings"))
        rules = config.load_rules(config.resolve_config_path(config_dir, "rules"))
        registry = config.load_registry(config.resolve_config_path(registry_dir, "licenses"))
        targets = config.load_targets(config.resolve_config_path(config_dir, "targets")).targets
        client = httpx.AsyncClient()

    reports_dir = output or settings.output.reports_dir

    async def _run() -> tuple[RunReport, Path, Path]:
        try:
            return await scan.scan_and_write(
                targets,
                settings,
                rules,
                registry,
                client=client,
                now=now,
                reports_dir=reports_dir,
                discover_ct=discover_subdomains and not demo_mode,
                max_pages_per_domain=max_pages,
            )
        finally:
            await client.aclose()

    report, json_path, html_path = asyncio.run(_run())
    _print_summary(report)
    console.print(f"\nJSON: [cyan]{json_path}[/]\nHTML: [cyan]{html_path}[/]")
    if csv_out:
        csv_path = json_path.with_name(json_path.name.removesuffix(".report.json") + ".csv")
        csv_path.write_text(build_csv(report), encoding="utf-8")
        console.print(f"CSV:  [cyan]{csv_path}[/]")


@app.command()
def report(
    run: Path = typer.Argument(..., help="Path to a JSON run report."),
    output: Path | None = typer.Option(None, "--output", help="HTML output path."),
) -> None:
    """Re-render the HTML dashboard from an existing JSON run."""

    run_report = load_run(run)
    html_path = output or run.with_suffix(".html")
    write_html(run_report, html_path)
    console.print(f"HTML: [cyan]{html_path}[/]")


def _print_diff(result: DiffResult) -> None:
    if not result.has_changes:
        console.print("[green]No changes since the previous run.[/]")
        return
    for f in result.new_findings:
        console.print(f"[red]NEW[/]      {f.family} ({f.owner or '—'}) score={f.score}")
    for f in result.resolved_findings:
        console.print(f"[green]RESOLVED[/] {f.family} ({f.owner or '—'})")
    for d in result.changed:
        console.print(
            f"[yellow]CHANGED[/]  {d.family} score {d.old_score}->{d.new_score} "
            f"domains {len(d.old_domains)}->{len(d.new_domains)}"
        )


@app.command()
def diff(
    previous: Path | None = typer.Argument(None, help="Previous run JSON (older)."),
    current: Path | None = typer.Argument(None, help="Current run JSON (newer)."),
    reports_dir: Path = typer.Option(Path("reports"), "--reports-dir", help="Auto-pick runs here."),
) -> None:
    """Compare two runs (defaults to the two most recent in --reports-dir)."""

    if previous is None or current is None:
        runs = latest_runs(reports_dir, limit=2)
        if len(runs) < 2:
            err_console.print("[red]Need two runs to diff.[/]")
            raise typer.Exit(1)
        current, previous = runs[0], runs[1]

    result = diff_runs(load_run(previous), load_run(current))
    _print_diff(result)
    raise typer.Exit(1 if result.new_findings else 0)


@registry_app.command("validate")
def registry_validate(
    registry_file: Path = typer.Option(
        Path("registry/licenses.yaml"), "--file", help="Registry YAML file."
    ),
    proofs_dir: Path = typer.Option(
        Path("registry/proofs"), "--proofs-dir", help="Proofs directory."
    ),
) -> None:
    """Validate the registry file and that referenced proof files exist."""

    registry: Registry = config.load_registry(registry_file)
    errors = validate_registry(registry, proofs_dir)
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/] registry OK ({len(registry.entries)} entries)")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (localhost only)."),
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
    config_dir: Path = typer.Option(Path("config"), "--config-dir", help="Config directory."),
    registry_dir: Path = typer.Option(Path("registry"), "--registry-dir", help="Registry dir."),
    reports_dir: Path = typer.Option(Path("reports"), "--reports-dir", help="Reports directory."),
) -> None:
    """Run the local web UI (requires the 'web' extra: uv sync --extra web)."""

    try:
        import uvicorn

        from fontsentry.web.server import create_app
    except ImportError:
        err_console.print("[red]Web extra not installed. Run:[/] uv sync --extra web")
        raise typer.Exit(1) from None

    if host not in {"127.0.0.1", "localhost"}:
        err_console.print("[red]Refusing to bind a non-localhost host (local-only by design).[/]")
        raise typer.Exit(1)

    application = create_app(
        reports_dir=reports_dir, config_dir=config_dir, registry_dir=registry_dir
    )
    console.print(f"FontSentry UI on [cyan]http://{host}:{port}[/]  (Ctrl+C to stop)")
    uvicorn.run(application, host=host, port=port, log_level="info")


@rules_app.command("validate")
def rules_validate(
    rules_file: Path = typer.Option(Path("config/rules.yaml"), "--file", help="Rules YAML file."),
) -> None:
    """Sanity-check the rule file (schema + known condition types)."""

    rules = config.load_rules(rules_file)
    errors = validate_rules(rules)
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/] rules OK ({len(rules.rules)} rules)")


if __name__ == "__main__":
    app()
