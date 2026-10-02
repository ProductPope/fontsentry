"""In-memory scan-job manager (lifecycle, unknown-id no-ops) and scan-job failures."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from fontsentry.web.jobs import JobManager, JobStatus
from fontsentry.web.scan_job import _run_scan_job


def test_job_lifecycle() -> None:
    jobs = JobManager()
    job = jobs.create("real")
    assert job.mode == "real"
    assert [j.id for j in jobs.active()] == [job.id]

    jobs.update_progress(job.id, "detect", 3, 10, "working")
    assert jobs.get(job.id).current == 3  # type: ignore[union-attr]

    jobs.mark_done(job.id, "fontsentry-x.report.json")
    assert jobs.active() == []  # no longer running
    done = jobs.get(job.id)
    assert done is not None and done.status is JobStatus.DONE
    assert done.run_id == "fontsentry-x.report.json"


def test_mark_error_moves_out_of_active() -> None:
    jobs = JobManager()
    job = jobs.create("demo")
    jobs.mark_error(job.id, "boom")
    assert jobs.active() == []
    assert jobs.get(job.id).error == "boom"  # type: ignore[union-attr]


def test_unknown_id_operations_are_noops() -> None:
    jobs = JobManager()
    # None of these should raise or create state.
    jobs.update_progress("nope", "p", 1, 2, "m")
    jobs.mark_done("nope", "r")
    jobs.mark_error("nope", "e")
    assert jobs.get("nope") is None
    assert jobs.active() == []


async def test_failed_scan_job_logs_traceback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # No config at all: the job must end in ERROR *and* leave a traceback in
    # the server log (the UI only shows the one-line message).
    jobs = JobManager()
    job = jobs.create("real")
    with caplog.at_level(logging.ERROR, logger="fontsentry.web.scan_job"):
        await _run_scan_job(jobs, job.id, "real", tmp_path, tmp_path / "none", tmp_path / "none")
    failed = jobs.get(job.id)
    assert failed is not None and failed.status is JobStatus.ERROR
    assert failed.error and "no config found" in failed.error
    record = next(r for r in caplog.records if job.id in r.getMessage())
    assert record.exc_info is not None
