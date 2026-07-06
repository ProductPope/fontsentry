"""Recurring audits via the OS scheduler — Windows Task Scheduler or cron.

The UI's "schedule a recurring audit" maps to a real OS scheduled task, so audits
run even when the UI is closed. Two backends, chosen by platform:

* **Windows** (`schtasks`) — tasks live under the ``FontSentry\\`` folder and invoke
  a generated ``.bat`` (avoids brittle nested-quote command strings).
* **Linux** (`cron`) — one ``crontab`` line per schedule, tagged with a
  ``# FontSentry:<name>`` marker so we only ever touch our own lines.

Other platforms (e.g. macOS) are unsupported; the API layer reports that. Each
backend is a pure arg/text builder around an injectable runner, so both are
testable on any OS without creating real tasks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

_TASK_FOLDER = "FontSentry"
_CRON_MARKER = "# FontSentry:"
# cron day-of-week numbers (0 = Sunday).
_CRON_DOW = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}


class Runner(Protocol):
    def __call__(
        self, args: list[str], *, input: str | None = None
    ) -> subprocess.CompletedProcess[str]: ...


class SchedulerError(Exception):
    """Raised when an OS scheduler invocation fails."""


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


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_supported() -> bool:
    return is_windows() or is_linux()


def _default_runner(
    args: list[str], *, input: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, input=input, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        # The scheduler binary (schtasks / crontab) isn't installed — degrade to a
        # non-zero result so listing returns empty and writes surface as an error.
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]}: not found")


# --- dispatch --------------------------------------------------------------


def create_schedule(
    spec: ScheduleSpec,
    *,
    tasks_dir: Path,
    working_dir: Path,
    python_exe: str | None = None,
    runner: Runner = _default_runner,
) -> ScheduleInfo:
    """Create (or replace) a scheduled task that runs an audit, on the host OS."""
    if is_windows():
        return _win_create_schedule(
            spec, tasks_dir=tasks_dir, working_dir=working_dir, python_exe=python_exe, runner=runner
        )
    if is_linux():
        return _cron_create_schedule(
            spec, tasks_dir=tasks_dir, working_dir=working_dir, python_exe=python_exe, runner=runner
        )
    raise SchedulerError("scheduling is only supported on Windows and Linux")


def delete_schedule(name: str, *, tasks_dir: Path, runner: Runner = _default_runner) -> None:
    if is_windows():
        _win_delete_schedule(name, tasks_dir=tasks_dir, runner=runner)
    elif is_linux():
        _cron_delete_schedule(name, tasks_dir=tasks_dir, runner=runner)
    else:
        raise SchedulerError("scheduling is only supported on Windows and Linux")


def list_schedules(runner: Runner = _default_runner) -> list[ScheduleInfo]:
    if is_windows():
        return _win_list_schedules(runner=runner)
    if is_linux():
        return _cron_list_schedules(runner=runner)
    return []


# --- Windows backend (schtasks) --------------------------------------------


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


def _win_create_schedule(
    spec: ScheduleSpec,
    *,
    tasks_dir: Path,
    working_dir: Path,
    python_exe: str | None = None,
    runner: Runner = _default_runner,
) -> ScheduleInfo:
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


def _win_delete_schedule(name: str, *, tasks_dir: Path, runner: Runner = _default_runner) -> None:
    result = runner(["schtasks", "/Delete", "/TN", _task_name(name), "/F"])
    if result.returncode != 0:
        raise SchedulerError(result.stderr.strip() or "schtasks /Delete failed")
    (tasks_dir / f"{name}.bat").unlink(missing_ok=True)


def _win_list_schedules(runner: Runner = _default_runner) -> list[ScheduleInfo]:
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


# --- Linux backend (cron) --------------------------------------------------


def _cron_expr(spec: ScheduleSpec) -> str:
    hour, minute = spec.time.split(":")
    dow = "*" if spec.frequency == "daily" else str(_CRON_DOW[spec.day_of_week])
    return f"{int(minute)} {int(hour)} * * {dow}"


def _cron_command(spec: ScheduleSpec, working_dir: Path, log_file: Path, python_exe: str) -> str:
    scan = f"'{python_exe}' -m fontsentry scan"
    if spec.mode == "demo":
        scan += " --demo"
    return f"cd '{working_dir}' && {scan} >> '{log_file}' 2>&1"


def _cron_line(spec: ScheduleSpec, working_dir: Path, log_file: Path, python_exe: str) -> str:
    command = _cron_command(spec, working_dir, log_file, python_exe)
    return f"{_cron_expr(spec)} {command} {_CRON_MARKER}{spec.name}"


def _cron_read(runner: Runner) -> str:
    """Current crontab text, or empty if the user has no crontab yet.

    Only the specific "no crontab for <user>" case may read as empty. Any other
    ``crontab -l`` failure (permissions, PAM, transient) must raise: treating it
    as empty would make the next install replace the user's entire crontab with
    only FontSentry lines.
    """
    result = runner(["crontab", "-l"])
    if result.returncode == 0:
        return result.stdout
    if "no crontab" in (result.stderr or "").lower():
        return ""
    raise SchedulerError(
        "could not read the current crontab; refusing to modify it: "
        + (result.stderr.strip() or "unknown error")
    )


def _cron_without(existing: str, name: str) -> list[str]:
    """Existing crontab lines with our marker for ``name`` removed."""
    marker = f"{_CRON_MARKER}{name}"
    return [line for line in existing.splitlines() if not line.rstrip().endswith(marker)]


def _cron_install(runner: Runner, lines: list[str]) -> None:
    text = "\n".join(line for line in lines if line.strip())
    if text:
        text += "\n"
    result = runner(["crontab", "-"], input=text)
    if result.returncode != 0:
        raise SchedulerError(result.stderr.strip() or "crontab update failed")


def _cron_create_schedule(
    spec: ScheduleSpec,
    *,
    tasks_dir: Path,
    working_dir: Path,
    python_exe: str | None = None,
    runner: Runner = _default_runner,
) -> ScheduleInfo:
    python_exe = python_exe or sys.executable
    tasks_dir.mkdir(parents=True, exist_ok=True)
    log_file = tasks_dir / f"{spec.name}.log"

    lines = _cron_without(_cron_read(runner), spec.name)
    lines.append(_cron_line(spec, working_dir, log_file, python_exe))
    _cron_install(runner, lines)
    return ScheduleInfo(name=spec.name, status=f"cron {_cron_expr(spec)}")


def _cron_delete_schedule(name: str, *, tasks_dir: Path, runner: Runner = _default_runner) -> None:
    _cron_install(runner, _cron_without(_cron_read(runner), name))
    (tasks_dir / f"{name}.log").unlink(missing_ok=True)


def _cron_list_schedules(runner: Runner = _default_runner) -> list[ScheduleInfo]:
    schedules: list[ScheduleInfo] = []
    for line in _cron_read(runner).splitlines():
        idx = line.rfind(_CRON_MARKER)
        if idx == -1:
            continue
        name = line[idx + len(_CRON_MARKER) :].strip()
        if not name:
            continue
        expr = " ".join(line.split()[:5])
        schedules.append(ScheduleInfo(name=name, status=f"cron {expr}"))
    return schedules
