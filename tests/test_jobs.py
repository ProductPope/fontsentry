"""In-memory scan-job manager: lifecycle and unknown-id no-ops."""

from __future__ import annotations

from fontsentry.web.jobs import JobManager, JobStatus


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
