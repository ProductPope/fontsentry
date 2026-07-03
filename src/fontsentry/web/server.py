"""FastAPI app for the local UI: list runs, fetch a run, diff, and start scans.

Security model (local, single-user): the server binds to 127.0.0.1 only and
rejects state-changing requests whose Origin is not localhost. No auth token —
only processes on this machine can reach it.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fontsentry import config, demo
from fontsentry.models import (
    DiffResult,
    Registry,
    RulesConfig,
    RunReport,
    RunSummary,
    TargetsConfig,
)
from fontsentry.registry.catalog import CATALOG
from fontsentry.report.csv_report import build_csv
from fontsentry.report.diff import diff_runs
from fontsentry.report.json_report import first_seen_map, load_run
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

# License proofs: a small allowlist of document/image types, capped in size.
_PROOF_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}
_MAX_PROOF_BYTES = 10 * 1024 * 1024

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


class FirstSeen(BaseModel):
    domain: str
    family: str
    first_seen: datetime


class KnownFont(BaseModel):
    family: str
    owner: str | None = None
    source: str  # "detected" (seen in an audit) | "catalog" (bundled suggestion)


class ScanRequest(BaseModel):
    mode: str = "demo"  # "demo" | "real"
    # Opt-in: also find public subdomains via Certificate Transparency logs and
    # crawl each as its own host (queries an external service; real mode only).
    discover_subdomains: bool = False
    # Per-scan override of the per-host page cap.
    max_pages_per_domain: int | None = Field(default=None, ge=1)


class ScanEstimate(BaseModel):
    eta_seconds: float | None  # None when there's no timed history to estimate from
    based_on_runs: int


class ScanStarted(BaseModel):
    job_id: str


def _web_dist() -> Path:
    return demo.repo_root() / "web" / "dist"


def _reports_for(reports_dir: Path, source: str) -> Path:
    """Reports live per data source: real runs in the root, demo runs in demo/.

    Keeps demo audits out of "your data" — they're a separate, isolated set.
    """

    return reports_dir / "demo" if source == "demo" else reports_dir


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
        allow_methods=["GET", "POST", "PUT", "DELETE"],
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
            # Browsers always send Sec-Fetch-Site; reject cross-site even when the
            # Origin header is absent (closes the null-Origin CSRF gap). Non-browser
            # clients (curl, tests) omit this header and are unaffected.
            if request.headers.get("sec-fetch-site") == "cross-site":
                return Response("cross-origin request rejected", status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runs")
    async def list_runs(source: str = "real") -> list[RunMeta]:
        metas: list[RunMeta] = []
        for path in sorted(
            _reports_for(reports_dir, source).glob("fontsentry-*.report.json"), reverse=True
        ):
            try:
                report = load_run(path)
            except (OSError, ValueError):
                continue
            metas.append(
                RunMeta(id=path.name, generated_at=report.generated_at, summary=report.summary)
            )
        return metas

    @app.get("/api/scan/estimate")
    async def scan_estimate(hosts: int, max_pages: int) -> ScanEstimate:
        # Estimate from recent runs' throughput (pages / wall-clock second).
        rates: list[float] = []
        for path in sorted(reports_dir.glob("fontsentry-*.report.json"), reverse=True)[:5]:
            try:
                rep = load_run(path)
            except (OSError, ValueError):
                continue
            pages = sum(d.pages_scanned for d in rep.domains)
            if rep.duration_seconds > 0 and pages > 0:
                rates.append(pages / rep.duration_seconds)
        if not rates:
            return ScanEstimate(eta_seconds=None, based_on_runs=0)
        rate = sum(rates) / len(rates)
        planned = max(0, hosts) * max(1, max_pages)
        return ScanEstimate(eta_seconds=round(planned / rate, 0), based_on_runs=len(rates))

    @app.get("/api/first-seen")
    async def get_first_seen(source: str = "real") -> list[FirstSeen]:
        # Computed from the report files on disk; no stored per-font history.
        return [
            FirstSeen(domain=domain, family=family, first_seen=ts)
            for (domain, family), ts in first_seen_map(_reports_for(reports_dir, source)).items()
        ]

    @app.get("/api/known-fonts")
    async def known_fonts() -> list[KnownFont]:
        # Suggestions for the registry form: fonts actually detected in the most
        # recent real audit (with any owner from metadata), plus a bundled catalog
        # of common families so there are suggestions before the first audit.
        # Keyed case-insensitively by family; detected entries win over catalog.
        by_key: dict[str, KnownFont] = {}
        reports = sorted(
            _reports_for(reports_dir, "real").glob("fontsentry-*.report.json"), reverse=True
        )
        if reports:
            for finding in load_run(reports[0]).findings:
                key = finding.family.strip().lower()
                if key and key not in by_key:
                    by_key[key] = KnownFont(
                        family=finding.family, owner=finding.owner, source="detected"
                    )
        for family, owner in CATALOG:
            key = family.strip().lower()
            if key not in by_key:
                by_key[key] = KnownFont(family=family, owner=owner, source="catalog")
        return sorted(by_key.values(), key=lambda k: k.family.lower())

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, source: str = "real") -> RunReport:
        path = _safe_run_path(_reports_for(reports_dir, source), run_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        return load_run(path)

    @app.get("/api/runs/{run_id}/export.csv")
    async def export_run_csv(run_id: str, source: str = "real") -> Response:
        path = _safe_run_path(_reports_for(reports_dir, source), run_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        filename = run_id.removesuffix(".report.json") + ".csv"
        return Response(
            content=build_csv(load_run(path)),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/runs/{run_id}/diff")
    async def get_run_diff(run_id: str, source: str = "real") -> DiffResult:
        # Diff a run against the one chronologically before it. An empty result
        # means either no earlier run exists or nothing changed.
        base = _reports_for(reports_dir, source)
        path = _safe_run_path(base, run_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        files = sorted(base.glob("fontsentry-*.report.json"))  # oldest first
        names = [p.name for p in files]
        idx = names.index(run_id) if run_id in names else -1
        if idx <= 0:
            return DiffResult()
        return diff_runs(load_run(files[idx - 1]), load_run(path))

    @app.get("/api/config/targets")
    async def get_targets() -> TargetsConfig:
        path = config_dir / "targets.yaml"
        if not path.exists():
            return TargetsConfig()
        try:
            return config.load_targets(path)
        except config.ConfigError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put("/api/config/targets")
    async def put_targets(targets: TargetsConfig) -> TargetsConfig:
        config.save_targets(config_dir / "targets.yaml", targets)
        return targets

    @app.get("/api/config/registry")
    async def get_registry() -> Registry:
        path = registry_dir / "licenses.yaml"
        if not path.exists():
            return Registry()
        try:
            return config.load_registry(path)
        except config.ConfigError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put("/api/config/registry")
    async def put_registry(registry: Registry) -> Registry:
        config.save_registry(registry_dir / "licenses.yaml", registry)
        return registry

    @app.get("/api/config/rules")
    async def get_rules() -> RulesConfig:
        # Rules have no empty default (scoring is required), so fall back to the
        # committed example when no real rules.yaml exists — same file the scan uses.
        try:
            return config.load_rules(config.resolve_config_path(config_dir, "rules"))
        except config.ConfigError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put("/api/config/rules")
    async def put_rules(rules: RulesConfig) -> RulesConfig:
        config.save_rules(config_dir / "rules.yaml", rules)
        return rules

    @app.post("/api/registry/proof")
    async def upload_proof(request: Request, file: UploadFile) -> dict[str, str]:
        # Never trust the client filename: keep only its basename, restrict the
        # charset, allowlist the extension, and cap the size. The result is what
        # gets stored in RegistryEntry.proof_path.
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > _MAX_PROOF_BYTES:
            raise HTTPException(status_code=413, detail="file too large (max 10 MB)")
        raw = Path(file.filename or "").name
        if Path(raw).suffix.lower() not in _PROOF_EXTS:
            raise HTTPException(status_code=400, detail="unsupported file type")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
        if not safe or safe.startswith("."):
            raise HTTPException(status_code=400, detail="invalid filename")
        # Stream and abort past the cap: never buffer the whole (possibly lying
        # about its length) upload into memory before rejecting it.
        data = bytearray()
        while chunk := await file.read(64 * 1024):
            data.extend(chunk)
            if len(data) > _MAX_PROOF_BYTES:
                raise HTTPException(status_code=413, detail="file too large (max 10 MB)")
        proofs = registry_dir / "proofs"
        proofs.mkdir(parents=True, exist_ok=True)
        (proofs / safe).write_bytes(data)
        return {"name": safe}

    @app.get("/api/registry/proof/{name}")
    async def get_proof(name: str) -> FileResponse:
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=400, detail="invalid proof name")
        proofs = (registry_dir / "proofs").resolve()
        path = (proofs / name).resolve()
        # Belt-and-suspenders: the resolved file must sit directly inside proofs/.
        if path.parent != proofs or not path.is_file():
            raise HTTPException(status_code=404, detail="proof not found")
        return FileResponse(path)

    @app.post("/api/scan")
    async def start_scan(request: ScanRequest) -> ScanStarted:
        if request.mode not in {"demo", "real"}:
            raise HTTPException(status_code=400, detail="mode must be 'demo' or 'real'")
        job = jobs.create(request.mode)
        # Fire-and-forget; status is polled via /api/jobs/{id}.
        task = asyncio.create_task(
            _run_scan_job(
                jobs,
                job.id,
                request.mode,
                reports_dir,
                config_dir,
                registry_dir,
                request.discover_subdomains,
                request.max_pages_per_domain,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return ScanStarted(job_id=job.id)

    @app.get("/api/jobs")
    async def list_active_jobs() -> list[Job]:
        # Running scans only — lets a freshly-loaded UI re-attach to a scan it
        # didn't start (kicked off from the CLI, another tab, or a prior session).
        return jobs.active()

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


async def _run_scan_job(
    jobs: JobManager,
    job_id: str,
    mode: str,
    reports_dir: Path,
    config_dir: Path,
    registry_dir: Path,
    discover_subdomains: bool = False,
    max_pages_per_domain: int | None = None,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    # CT lookup queries an external service, so only for real scans (the demo
    # runs offline against a filesystem transport).
    discover_ct = discover_subdomains and mode == "real"

    def on_progress(phase: str, current: int, total: int, message: str) -> None:
        jobs.update_progress(job_id, phase, current, total, message)

    # Config loading is inside the try so a bad rules.yaml / targets.yaml marks the
    # job as error instead of leaving it stuck "running" forever (and leaking the
    # HTTP client). client stays None until created, so finally can guard it.
    client: httpx.AsyncClient | None = None
    try:
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

        _report, json_path, _html = await scan_and_write(
            targets,
            settings,
            rules,
            registry,
            client=client,
            now=now,
            reports_dir=_reports_for(reports_dir, mode),
            progress=on_progress,
            discover_ct=discover_ct,
            max_pages_per_domain=max_pages_per_domain,
        )
        jobs.mark_done(job_id, json_path.name)
    except Exception as exc:
        jobs.mark_error(job_id, str(exc))
    finally:
        if client is not None:
            await client.aclose()
