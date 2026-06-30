"""Recurring audits via the Windows Task Scheduler (`schtasks`).

The UI's "schedule a recurring audit" maps to a real OS scheduled task, so audits
run even when the UI is closed. Tasks live under the ``FontSentry\\`` folder and
invoke a generated ``.bat`` (avoids brittle nested-quote command strings).

This backend is Windows-only by design; the API layer reports that on other
platforms. The core is a pure arg-builder around an injectable runner, so it is
testable on any OS.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_TASK_FOLDER = "FontSentry"

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class SchedulerError(Exception):
    """Raised when a schtasks invocation fails."""


class ScheduleSpec(BaseModel):
    name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9 _-]+$")
    frequency: Literal["daily", "weekly"] = "weekly"
    time: str = Field(default="06:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    day_of_week: Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] = "MON"
    mode: Literal["demo", "real"] = "real"


class ScheduleInfo(BaseModel):
    name: str
    next_run: str | None = None
    status: str | None = None


def is_windows() -> bool:
    return sys.platform == "win32"


def _default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _task_name(name: str) -> str:
    return f"{_TASK_FOLDER}\\{name}"


def _write_launcher(
    spec: ScheduleSpec, tasks_dir: Path, working_dir: Path, python_exe: str
) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    bat = tasks_dir / f"{spec.name}.bat"
    scan_cmd = f'"{python_exe}" -m fontsentry scan'
    if spec.mode == "demo":
        scan_cmd += " --demo"
    bat.write_text(
        f'@echo off\r\ncd /d "{working_dir}"\r\n{scan_cmd}\r\n',
        encoding="utf-8",
    )
    return bat


def create_schedule(
    spec: ScheduleSpec,
    *,
    tasks_dir: Path,
    working_dir: Path,
    python_exe: str | None = None,
    runner: Runner = _default_runner,
) -> ScheduleInfo:
    """Create (or replace, via /F) a scheduled task that runs an audit."""

    python_exe = python_exe or sys.executable
    launcher = _write_launcher(spec, tasks_dir, working_dir, python_exe)

    args = [
        "schtasks",
        "/Create",
        "/TN",
        _task_name(spec.name),
        "/TR",
        str(launcher),
        "/SC",
        "DAILY" if spec.frequency == "daily" else "WEEKLY",
        "/ST",
        spec.time,
        "/F",
    ]
    if spec.frequency == "weekly":
        args += ["/D", spec.day_of_week]

    result = runner(args)
    if result.returncode != 0:
        raise SchedulerError(result.stderr.strip() or "schtasks /Create failed")
    return ScheduleInfo(name=spec.name)


def delete_schedule(name: str, *, tasks_dir: Path, runner: Runner = _default_runner) -> None:
    result = runner(["schtasks", "/Delete", "/TN", _task_name(name), "/F"])
    if result.returncode != 0:
        raise SchedulerError(result.stderr.strip() or "schtasks /Delete failed")
    launcher = tasks_dir / f"{name}.bat"
    launcher.unlink(missing_ok=True)


def list_schedules(runner: Runner = _default_runner) -> list[ScheduleInfo]:
    """List FontSentry scheduled tasks by parsing schtasks CSV output."""

    result = runner(["schtasks", "/Query", "/FO", "CSV", "/NH"])
    if result.returncode != 0:
        return []

    schedules: list[ScheduleInfo] = []
    prefix = f"\\{_TASK_FOLDER}\\"
    for row in result.stdout.splitlines():
        fields = [f.strip().strip('"') for f in row.split('","')]
        if not fields:
            continue
        task_name = fields[0].strip('"')
        if not task_name.startswith(prefix):
            continue
        schedules.append(
            ScheduleInfo(
                name=task_name[len(prefix) :],
                next_run=fields[1] if len(fields) > 1 else None,
                status=fields[2] if len(fields) > 2 else None,
            )
        )
    return schedules
