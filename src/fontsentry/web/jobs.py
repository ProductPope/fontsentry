"""In-memory tracking of background scan jobs.

A scan runs asynchronously after `POST /api/scan` returns; the UI polls
`GET /api/jobs/{id}` for status. State is intentionally in-process and ephemeral —
the durable record of a scan is its JSON report on disk.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.RUNNING
    mode: str = "real"  # "real" | "demo" — which data set the scan ran on
    run_id: str | None = None
    error: str | None = None
    # Live progress, updated as the scan moves through its phases.
    phase: str = ""  # "discover" | "detect" | "score" | "report"
    message: str = ""
    current: int = 0  # units done in the current phase
    total: int = 0  # units total in the current phase (0 = unknown/indeterminate)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, mode: str = "real") -> Job:
        job = Job(id=uuid.uuid4().hex, mode=mode)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def active(self) -> list[Job]:
        """Currently-running jobs, so a freshly-loaded UI can re-attach to a scan
        it did not start itself (e.g. one kicked off from the CLI or another tab)."""
        return [j for j in self._jobs.values() if j.status is JobStatus.RUNNING]

    def update_progress(
        self, job_id: str, phase: str, current: int, total: int, message: str
    ) -> None:
        if job := self._jobs.get(job_id):
            job.phase = phase
            job.current = current
            job.total = total
            job.message = message

    def mark_done(self, job_id: str, run_id: str) -> None:
        if job := self._jobs.get(job_id):
            job.status = JobStatus.DONE
            job.run_id = run_id

    def mark_error(self, job_id: str, message: str) -> None:
        if job := self._jobs.get(job_id):
            job.status = JobStatus.ERROR
            job.error = message
