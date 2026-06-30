"""Scheduler arg-building, launcher generation, and CSV parsing.

Uses an injected fake runner so no real `schtasks` task is created — runs on any OS.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from fontsentry.web.scheduler import (
    SchedulerError,
    ScheduleSpec,
    create_schedule,
    delete_schedule,
    list_schedules,
)


class FakeRunner:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)


def test_create_weekly_builds_args_and_launcher(tmp_path: Path) -> None:
    runner = FakeRunner()
    spec = ScheduleSpec(name="weekly-audit", frequency="weekly", time="06:30", day_of_week="MON")
    create_schedule(
        spec, tasks_dir=tmp_path, working_dir=tmp_path, python_exe="py.exe", runner=runner
    )

    args = runner.calls[0]
    assert args[:4] == ["schtasks", "/Create", "/TN", "FontSentry\\weekly-audit"]
    assert "/SC" in args and args[args.index("/SC") + 1] == "WEEKLY"
    assert args[args.index("/D") + 1] == "MON"
    assert args[args.index("/ST") + 1] == "06:30"
    assert "/F" in args

    bat = tmp_path / "weekly-audit.bat"
    assert bat.exists()
    assert "-m fontsentry scan" in bat.read_text()


def test_create_daily_omits_day(tmp_path: Path) -> None:
    runner = FakeRunner()
    create_schedule(
        ScheduleSpec(name="daily", frequency="daily", time="09:00"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=runner,
    )
    args = runner.calls[0]
    assert args[args.index("/SC") + 1] == "DAILY"
    assert "/D" not in args


def test_demo_mode_launcher_has_flag(tmp_path: Path) -> None:
    create_schedule(
        ScheduleSpec(name="demo-run", mode="demo"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=FakeRunner(),
    )
    assert "scan --demo" in (tmp_path / "demo-run.bat").read_text()


def test_create_failure_raises(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=1, stderr="access denied")
    with pytest.raises(SchedulerError, match="access denied"):
        create_schedule(
            ScheduleSpec(name="x"), tasks_dir=tmp_path, working_dir=tmp_path, runner=runner
        )


def test_delete_removes_task_and_launcher(tmp_path: Path) -> None:
    bat = tmp_path / "gone.bat"
    bat.write_text("@echo off", encoding="utf-8")
    runner = FakeRunner()
    delete_schedule("gone", tasks_dir=tmp_path, runner=runner)
    assert runner.calls[0] == ["schtasks", "/Delete", "/TN", "FontSentry\\gone", "/F"]
    assert not bat.exists()


def test_list_filters_fontsentry_tasks() -> None:
    stdout = (
        '"\\FontSentry\\weekly-audit","6/7/2026 6:00:00 AM","Ready"\n'
        '"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","N/A","Ready"\n'
        '"\\FontSentry\\nightly","6/1/2026 9:00:00 AM","Ready"\n'
    )
    schedules = list_schedules(runner=FakeRunner(stdout=stdout))
    names = {s.name for s in schedules}
    assert names == {"weekly-audit", "nightly"}
    weekly = next(s for s in schedules if s.name == "weekly-audit")
    assert weekly.status == "Ready"


def test_list_returns_empty_on_query_failure() -> None:
    assert list_schedules(runner=FakeRunner(returncode=1)) == []


def test_spec_validation() -> None:
    with pytest.raises(ValidationError):
        ScheduleSpec(name="bad name!")  # illegal char
    with pytest.raises(ValidationError):
        ScheduleSpec(name="ok", time="25:00")  # invalid time
