"""Filesystem-path helpers for the web layer, shared by the app and the scan job."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from fontsentry import demo


def _web_dist() -> Path:
    return demo.repo_root() / "web" / "dist"


def _reports_for(reports_dir: Path, source: str) -> Path:
    """Reports live per data source: real runs in the root, demo runs in demo/.

    Keeps demo audits out of "your data" — they're a separate, isolated set.
    """

    return reports_dir / "demo" if source == "demo" else reports_dir


def _safe_run_path(reports_dir: Path, run_id: str) -> Path:
    """Resolve a run id to a report file inside reports_dir. Resolve-and-contain
    (not string checks): the resolved path must sit directly in reports_dir and be
    a .report.json — this also blocks absolute/encoded/drive-relative escapes."""

    if not run_id.endswith(".report.json"):
        raise HTTPException(status_code=400, detail="invalid run id")
    base = reports_dir.resolve()
    path = (base / run_id).resolve()
    if path.parent != base:
        raise HTTPException(status_code=400, detail="invalid run id")
    return path
