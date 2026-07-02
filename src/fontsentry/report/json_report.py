"""Build, write, and load the JSON run report — the source of truth for a scan.

Every other output (HTML, diff) derives from a :class:`RunReport`, so this stays
deliberately simple: assemble the summary, serialize via pydantic, and persist a
timestamped file per run.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from fontsentry.models import (
    DomainReport,
    Finding,
    FindingStatus,
    RiskBand,
    RunReport,
    RunSummary,
)

_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def build_summary(findings: list[Finding]) -> RunSummary:
    band_counts: Counter[RiskBand] = Counter(f.band for f in findings)
    open_count = sum(1 for f in findings if f.status is FindingStatus.OPEN)
    return RunSummary(
        total_findings=len(findings),
        open_findings=open_count,
        resolved_findings=len(findings) - open_count,
        by_band={band: band_counts.get(band, 0) for band in RiskBand},
    )


def build_report(
    findings: list[Finding],
    generated_at: datetime,
    domains: list[DomainReport] | None = None,
) -> RunReport:
    return RunReport(
        generated_at=generated_at,
        summary=build_summary(findings),
        findings=findings,
        domains=domains or [],
    )


def run_filename(generated_at: datetime) -> str:
    return f"fontsentry-{generated_at.strftime(_TIMESTAMP_FORMAT)}.report.json"


def write_run(report: RunReport, reports_dir: Path) -> Path:
    """Write the report to a timestamped file under ``reports_dir`` and return its path."""

    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / run_filename(report.generated_at)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_run(path: Path) -> RunReport:
    return RunReport.model_validate_json(path.read_text(encoding="utf-8"))


def first_seen_map(reports_dir: Path) -> dict[tuple[str, str], datetime]:
    """Earliest ``generated_at`` per ``(domain, family)`` across all run reports.

    Derived on the fly from the timestamped report files already written per run —
    no per-font history is stored anywhere else. Unreadable files are skipped.
    """

    earliest: dict[tuple[str, str], datetime] = {}
    for path in sorted(reports_dir.glob("fontsentry-*.report.json")):
        try:
            report = load_run(path)
        except (OSError, ValueError):
            continue
        for domain in report.domains:
            for font in domain.fonts:
                key = (domain.domain, font.family)
                current = earliest.get(key)
                if current is None or report.generated_at < current:
                    earliest[key] = report.generated_at
    return earliest


def latest_runs(reports_dir: Path, limit: int = 2) -> list[Path]:
    """Return the most recent run files (newest first), by filename timestamp."""

    runs = sorted(reports_dir.glob("fontsentry-*.report.json"), reverse=True)
    return runs[:limit]
