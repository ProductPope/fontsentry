"""FastAPI app for the local UI: list runs, fetch a run, diff, and start scans.

Security model (local, single-user): the server binds to 127.0.0.1 only and
rejects state-changing requests whose Origin is not localhost. No auth token —
only processes on this machine can reach it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fontsentry import config, demo
from fontsentry.models import DiffResult, RunReport, RunSummary
from fontsentry.report.diff import diff_runs
from fontsentry.report.json_report import load_run
from fontsentry.scan import scan_and_write
from fontsentry.web.jobs import Job, JobManager
from fontsentry.web.scheduler import (
    ScheduleInfo,
    SchedulerError,
    ScheduleSpec,
    create_schedule,
    delete_schedule,
    is_windows,
    list_schedules,
)

# Keep strong references to in-flight scan tasks so they are not garbage-collected.
_background_tasks: set[asyncio.Task[None]] = set()

_ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


class RunMeta(BaseModel):
    id: str
    generated_at: datetime
    summary: RunSummary


class ScanRequest(BaseModel):
    mode: str = "demo"  # "demo" | "real"


class ScanStarted(BaseModel):
    job_id: str


def _web_dist() -> Path:
    return demo.repo_root() / "web" / "dist"


def create_app(
    *,
    reports_dir: Path = Path("reports"),
    config_dir: Path = Path("config"),
    registry_dir: Path = Path("registry"),
) -> FastAPI:
    app = FastAPI(title="FontSentry", docs_url=None, redoc_url=None)
    jobs = JobManager()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_LOCAL_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _origin_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).hostname not in _ALLOWED_HOSTS:
                return Response("cross-origin request rejected", status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runs")
    async def list_runs() -> list[RunMeta]:
        metas: list[RunMeta] = []
        for path in sorted(reports_dir.glob("*.report.json"), reverse=True):
            try:
                report = load_run(path)
            except (OSError, ValueError):
                continue
            metas.append(
                RunMeta(id=path.name, generated_at=report.generated_at, summary=report.summary)
            )
        return metas

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> RunReport:
        path = _safe_run_path(reports_dir, run_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        return load_run(path)

    @app.get("/api/diff")
    async def get_diff(previous: str, current: str) -> DiffResult:
        prev_path = _safe_run_path(reports_dir, previous)
        cur_path = _safe_run_path(reports_dir, current)
        if not prev_path.exists() or not cur_path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        return diff_runs(load_run(prev_path), load_run(cur_path))

    @app.post("/api/scan")
    async def start_scan(request: ScanRequest) -> ScanStarted:
        if request.mode not in {"demo", "real"}:
            raise HTTPException(status_code=400, detail="mode must be 'demo' or 'real'")
        job = jobs.create()
        # Fire-and-forget; status is polled via /api/jobs/{id}.
        task = asyncio.create_task(
            _run_scan_job(jobs, job.id, request.mode, reports_dir, config_dir, registry_dir)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return ScanStarted(job_id=job.id)

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    tasks_dir = Path(".fontsentry-tasks")

    @app.get("/api/schedules")
    async def get_schedules() -> list[ScheduleInfo]:
        if not is_windows():
            return []
        return list_schedules()

    @app.post("/api/schedules", status_code=201)
    async def create_schedule_endpoint(spec: ScheduleSpec) -> ScheduleInfo:
        if not is_windows():
            raise HTTPException(status_code=501, detail="scheduling is only supported on Windows")
        try:
            return create_schedule(spec, tasks_dir=tasks_dir, working_dir=demo.repo_root())
        except SchedulerError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/schedules/{name}")
    async def delete_schedule_endpoint(name: str) -> dict[str, str]:
        if not is_windows():
            raise HTTPException(status_code=501, detail="scheduling is only supported on Windows")
        try:
            delete_schedule(name, tasks_dir=tasks_dir)
        except SchedulerError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"deleted": name}

    dist = _web_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    else:

        @app.get("/")
        async def _no_ui() -> Response:
            return Response(
                "UI not built yet. Run: cd web && npm install && npm run build",
                media_type="text/plain",
            )

    return app


def _safe_run_path(reports_dir: Path, run_id: str) -> Path:
    """Resolve a run id to a path inside reports_dir, rejecting traversal."""

    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run id")
    return reports_dir / run_id


async def _run_scan_job(
    jobs: JobManager,
    job_id: str,
    mode: str,
    reports_dir: Path,
    config_dir: Path,
    registry_dir: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    if mode == "demo":
        settings = demo.demo_settings()
        rules = config.load_rules(config.resolve_config_path(config_dir, "rules"))
        registry = config.load_registry(demo.demo_registry_path())
        targets = demo.demo_targets()
        client = demo.demo_client()
    else:
        settings = config.load_settings(config.resolve_config_path(config_dir, "settings"))
        rules = config.load_rules(config.resolve_config_path(config_dir, "rules"))
        registry = config.load_registry(config.resolve_config_path(registry_dir, "licenses"))
        targets = config.load_targets(config.resolve_config_path(config_dir, "targets")).targets
        client = httpx.AsyncClient()

    try:
        _report, json_path, _html = await scan_and_write(
            targets, settings, rules, registry, client=client, now=now, reports_dir=reports_dir
        )
        jobs.mark_done(job_id, json_path.name)
    except Exception as exc:
        jobs.mark_error(job_id, str(exc))
    finally:
        await client.aclose()
