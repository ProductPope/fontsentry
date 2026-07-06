"""Scheduler arg/text building for both backends (schtasks + cron).

Uses injected fake runners so no real task is created — runs on any OS.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from fontsentry.web import scheduler
from fontsentry.web.scheduler import (
    SchedulerError,
    ScheduleSpec,
    _cron_create_schedule,
    _cron_delete_schedule,
    _cron_expr,
    _cron_list_schedules,
    _win_create_schedule,
    _win_delete_schedule,
    _win_list_schedules,
    create_schedule,
)


class FakeRunner:
    """schtasks-style runner: one canned result for every call."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], *, input: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)


class CronRunner:
    """cron runner: returns `existing` for `crontab -l`, captures `crontab -` input."""

    def __init__(
        self,
        existing: str = "",
        list_rc: int = 0,
        install_rc: int = 0,
        list_stderr: str = "",
    ) -> None:
        self.existing = existing
        self.list_rc = list_rc
        self.install_rc = install_rc
        self.list_stderr = list_stderr
        self.installed: str | None = None
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], *, input: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:2] == ["crontab", "-l"]:
            return subprocess.CompletedProcess(args, self.list_rc, self.existing, self.list_stderr)
        if args == ["crontab", "-"]:
            self.installed = input
            return subprocess.CompletedProcess(args, self.install_rc, "", "cron write failed")
        return subprocess.CompletedProcess(args, 0, "", "")


# --- Windows backend -------------------------------------------------------


def test_win_create_weekly_builds_args_and_launcher(tmp_path: Path) -> None:
    runner = FakeRunner()
    spec = ScheduleSpec(name="weekly-audit", frequency="weekly", time="06:30", day_of_week="MON")
    _win_create_schedule(
        spec, tasks_dir=tmp_path, working_dir=tmp_path, python_exe="py.exe", runner=runner
    )

    args = runner.calls[0]
    assert args[:4] == ["schtasks", "/Create", "/TN", "FontSentry\\weekly-audit"]
    assert args[args.index("/SC") + 1] == "WEEKLY"
    assert args[args.index("/D") + 1] == "MON"
    assert args[args.index("/ST") + 1] == "06:30"
    assert (tmp_path / "weekly-audit.bat").exists()


def test_win_create_daily_omits_day(tmp_path: Path) -> None:
    runner = FakeRunner()
    _win_create_schedule(
        ScheduleSpec(name="daily", frequency="daily", time="09:00"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=runner,
    )
    args = runner.calls[0]
    assert args[args.index("/SC") + 1] == "DAILY"
    assert "/D" not in args


def test_win_demo_mode_launcher_has_flag(tmp_path: Path) -> None:
    _win_create_schedule(
        ScheduleSpec(name="demo-run", mode="demo"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=FakeRunner(),
    )
    assert "scan --demo" in (tmp_path / "demo-run.bat").read_text()


def test_win_create_failure_raises(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=1, stderr="access denied")
    with pytest.raises(SchedulerError, match="access denied"):
        _win_create_schedule(
            ScheduleSpec(name="x"), tasks_dir=tmp_path, working_dir=tmp_path, runner=runner
        )


def test_win_delete_removes_task_and_launcher(tmp_path: Path) -> None:
    bat = tmp_path / "gone.bat"
    bat.write_text("@echo off", encoding="utf-8")
    runner = FakeRunner()
    _win_delete_schedule("gone", tasks_dir=tmp_path, runner=runner)
    assert runner.calls[0] == ["schtasks", "/Delete", "/TN", "FontSentry\\gone", "/F"]
    assert not bat.exists()


def test_win_list_filters_fontsentry_tasks() -> None:
    stdout = (
        '"\\FontSentry\\weekly-audit","6/7/2026 6:00:00 AM","Ready"\n'
        '"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","N/A","Ready"\n'
        '"\\FontSentry\\nightly","6/1/2026 9:00:00 AM","Ready"\n'
    )
    schedules = _win_list_schedules(runner=FakeRunner(stdout=stdout))
    assert {s.name for s in schedules} == {"weekly-audit", "nightly"}


# --- cron backend ----------------------------------------------------------


def test_cron_expr_weekly_and_daily() -> None:
    assert _cron_expr(
        ScheduleSpec(name="a", frequency="weekly", time="06:30", day_of_week="MON")
    ) == ("30 6 * * 1")
    assert _cron_expr(ScheduleSpec(name="a", frequency="daily", time="09:00")) == "0 9 * * *"
    assert _cron_expr(ScheduleSpec(name="a", frequency="weekly", day_of_week="SUN")) == "0 6 * * 0"


def test_cron_create_appends_marked_line(tmp_path: Path) -> None:
    runner = CronRunner(existing="0 0 * * * /usr/bin/other  # someone else\n")
    _cron_create_schedule(
        ScheduleSpec(name="nightly", frequency="daily", time="03:15"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        python_exe="/venv/bin/python",
        runner=runner,
    )
    installed = runner.installed or ""
    assert "# someone else" in installed  # unrelated line preserved
    assert "# FontSentry:nightly" in installed
    assert "15 3 * * *" in installed
    assert "-m fontsentry scan" in installed


def test_cron_create_replaces_own_prior_line(tmp_path: Path) -> None:
    existing = "5 5 * * * cd '/x' && old  # FontSentry:nightly\n0 0 * * * keep  # keep\n"
    runner = CronRunner(existing=existing)
    _cron_create_schedule(
        ScheduleSpec(name="nightly", frequency="daily", time="03:00"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=runner,
    )
    installed = runner.installed or ""
    assert installed.count("# FontSentry:nightly") == 1  # replaced, not duplicated
    assert "5 5 * * *" not in installed  # old line gone
    assert "# keep" in installed


def test_cron_create_no_existing_crontab(tmp_path: Path) -> None:
    runner = CronRunner(list_rc=1, list_stderr="no crontab for user")
    _cron_create_schedule(
        ScheduleSpec(name="w", frequency="weekly", time="06:00", day_of_week="FRI"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=runner,
    )
    assert (runner.installed or "").strip().endswith("# FontSentry:w")


@pytest.mark.parametrize("stderr", ["permission denied", ""])
def test_cron_read_failure_refuses_to_write(tmp_path: Path, stderr: str) -> None:
    # Regression: a failing `crontab -l` (permissions, PAM, transient) used to
    # read as "no crontab yet", so the next install replaced the user's whole
    # crontab with only FontSentry lines. Only "no crontab for <user>" may be
    # treated as empty; anything else must refuse to touch the crontab at all.
    runner = CronRunner(existing="0 1 * * * someone-elses-job\n", list_rc=1, list_stderr=stderr)
    with pytest.raises(SchedulerError, match="refusing"):
        _cron_create_schedule(
            ScheduleSpec(name="w"), tasks_dir=tmp_path, working_dir=tmp_path, runner=runner
        )
    with pytest.raises(SchedulerError, match="refusing"):
        _cron_delete_schedule("w", tasks_dir=tmp_path, runner=runner)
    assert runner.installed is None  # `crontab -` was never invoked


def test_cron_demo_mode_in_command(tmp_path: Path) -> None:
    runner = CronRunner()
    _cron_create_schedule(
        ScheduleSpec(name="d", mode="demo"),
        tasks_dir=tmp_path,
        working_dir=tmp_path,
        runner=runner,
    )
    assert "scan --demo" in (runner.installed or "")


def test_cron_install_failure_raises(tmp_path: Path) -> None:
    runner = CronRunner(install_rc=1)
    with pytest.raises(SchedulerError):
        _cron_create_schedule(
            ScheduleSpec(name="x"), tasks_dir=tmp_path, working_dir=tmp_path, runner=runner
        )


def test_cron_delete_drops_only_our_line(tmp_path: Path) -> None:
    log = tmp_path / "gone.log"
    log.write_text("run", encoding="utf-8")
    existing = "0 0 * * * keep  # keep\n1 1 * * * cd '/x' && s  # FontSentry:gone\n"
    runner = CronRunner(existing=existing)
    _cron_delete_schedule("gone", tasks_dir=tmp_path, runner=runner)
    installed = runner.installed or ""
    assert "# FontSentry:gone" not in installed
    assert "# keep" in installed
    assert not log.exists()


def test_cron_list_parses_markers() -> None:
    existing = (
        "0 0 * * * keep  # keep\n"
        "30 6 * * 1 cd '/x' && s  # FontSentry:weekly\n"
        "0 3 * * * cd '/x' && s  # FontSentry:nightly\n"
    )
    schedules = _cron_list_schedules(runner=CronRunner(existing=existing))
    assert {s.name for s in schedules} == {"weekly", "nightly"}
    weekly = next(s for s in schedules if s.name == "weekly")
    assert weekly.status == "cron 30 6 * * 1"


# --- dispatch + validation -------------------------------------------------


def test_create_dispatches_to_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "is_windows", lambda: False)
    monkeypatch.setattr(scheduler, "is_linux", lambda: True)
    runner = CronRunner()
    create_schedule(
        ScheduleSpec(name="via-dispatch"), tasks_dir=tmp_path, working_dir=tmp_path, runner=runner
    )
    assert "# FontSentry:via-dispatch" in (runner.installed or "")


def test_create_unsupported_platform_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "is_windows", lambda: False)
    monkeypatch.setattr(scheduler, "is_linux", lambda: False)
    with pytest.raises(SchedulerError, match="Windows and Linux"):
        create_schedule(
            ScheduleSpec(name="x"), tasks_dir=tmp_path, working_dir=tmp_path, runner=FakeRunner()
        )


def test_spec_validation() -> None:
    with pytest.raises(ValidationError):
        ScheduleSpec(name="bad name!")
    with pytest.raises(ValidationError):
        ScheduleSpec(name="ok", time="25:00")
