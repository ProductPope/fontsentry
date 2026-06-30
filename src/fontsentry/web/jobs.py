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
    run_id: str | None = None
    error: str | None = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def mark_done(self, job_id: str, run_id: str) -> None:
        if job := self._jobs.get(job_id):
            job.status = JobStatus.DONE
            job.run_id = run_id

    def mark_error(self, job_id: str, message: str) -> None:
        if job := self._jobs.get(job_id):
            job.status = JobStatus.ERROR
            job.error = message
