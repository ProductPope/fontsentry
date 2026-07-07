"""FastAPI app for the local UI: list runs, fetch a run, diff, and start scans.

Security model (local, single-user): the server binds to 127.0.0.1 only and
rejects state-changing requests whose Origin is not localhost. No auth token —
only processes on this machine can reach it.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fontsentry import config, demo
from fontsentry.models import (
    DiffResult,
    Registry,
    RulesConfig,
    RunReport,
    TargetsConfig,
)
from fontsentry.registry.catalog import CATALOG
from fontsentry.registry.portable import registry_from_csv, registry_to_csv
from fontsentry.registry.registry import merge_registries
from fontsentry.report.csv_report import build_csv
from fontsentry.report.diff import diff_runs
from fontsentry.report.json_report import first_seen_map, load_run
from fontsentry.web.jobs import Job, JobManager
from fontsentry.web.paths import _reports_for, _safe_run_path, _web_dist
from fontsentry.web.scan_job import _run_scan_job
from fontsentry.web.scheduler import (
    ScheduleInfo,
    SchedulerError,
    ScheduleSpec,
    create_schedule,
    delete_schedule,
    is_supported,
    is_valid_schedule_name,
    list_schedules,
)
from fontsentry.web.schemas import (
    FirstSeen,
    KnownFont,
    RegistryImportResult,
    RunMeta,
    ScanEstimate,
    ScanRequest,
    ScanStarted,
)
from fontsentry.web.workspace import (
    BackupInfo,
    WorkspaceError,
    build_workspace_zip,
    list_backups,
    read_backup,
    restore_workspace_zip,
    snapshot_filename,
    write_snapshot,
)

logger = logging.getLogger(__name__)

# Keep strong references to in-flight scan tasks so they are not garbage-collected.
_background_tasks: set[asyncio.Task[None]] = set()

# License proofs: a small allowlist of document/image types, capped in size.
_PROOF_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}
_MAX_PROOF_BYTES = 10 * 1024 * 1024

# Request bodies are user-supplied files ("a backup someone sent me"), so every
# state-changing request is size-capped: workspace zips may be large (reports),
# everything else is small YAML/JSON/CSV.
_MAX_BODY_BYTES = 10 * 1024 * 1024
_MAX_IMPORT_BODY_BYTES = 250 * 1024 * 1024

_ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def create_app(
    *,
    reports_dir: Path = Path("reports"),
    config_dir: Path = Path("config"),
    registry_dir: Path = Path("registry"),
    backups_dir: Path = Path("backups"),
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
        # DNS-rebinding defense: after an attacker's domain re-resolves to
        # 127.0.0.1, the browser sends `Host: attacker.example` and same-origin
        # GETs could read the API — including the whole-workspace export. Only
        # localhost Hosts are served: every request, not just state changes.
        host = urlparse(f"//{request.headers.get('host', '')}").hostname
        if host not in _ALLOWED_HOSTS:
            return Response("invalid Host header", status_code=400)
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

    @app.middleware("http")
    async def _body_size_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Fast path on the declared length; the raw-body import endpoints also
        # enforce the cap while streaming, in case the header lies or is absent.
        if request.method in {"POST", "PUT", "PATCH"}:
            limit = (
                _MAX_IMPORT_BODY_BYTES
                if request.url.path.startswith("/api/workspace/")
                else _MAX_BODY_BYTES
            )
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > limit:
                return Response("request body too large", status_code=413)
        return await call_next(request)

    async def _read_body(request: Request, limit: int) -> bytes:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(status_code=413, detail="request body too large")
        return bytes(data)

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
            except (OSError, ValueError) as exc:
                logger.warning("skipping unreadable report %s: %s", path.name, exc)
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
            except (OSError, ValueError) as exc:
                logger.warning("skipping unreadable report %s: %s", path.name, exc)
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
            try:
                latest = load_run(reports[0])
            except (OSError, ValueError) as exc:
                logger.warning("skipping unreadable report %s: %s", reports[0].name, exc)
                latest = None
            for finding in latest.findings if latest else []:
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

    @app.post("/api/config/registry/import")
    async def import_registry(incoming: Registry) -> RegistryImportResult:
        # Merge (upsert by owner+family) into the current registry rather than
        # replacing it, so an import never silently drops existing licenses.
        path = registry_dir / "licenses.yaml"
        try:
            current = config.load_registry(path) if path.exists() else Registry()
        except config.ConfigError:
            current = Registry()
        merged, added, replaced = merge_registries(current, incoming)
        config.save_registry(path, merged)
        return RegistryImportResult(registry=merged, added=added, replaced=replaced)

    def _load_registry_or_empty() -> Registry:
        path = registry_dir / "licenses.yaml"
        try:
            return config.load_registry(path) if path.exists() else Registry()
        except config.ConfigError:
            return Registry()

    @app.get("/api/config/registry/export.csv")
    async def export_registry_csv() -> Response:
        return Response(
            content=registry_to_csv(_load_registry_or_empty()),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="fontsentry-registry.csv"'},
        )

    @app.post("/api/config/registry/import.csv")
    async def import_registry_csv(request: Request) -> RegistryImportResult:
        # Excel writes a UTF-8 BOM; utf-8-sig strips it so the first column header
        # isn't read as "﻿owner".
        text = (await _read_body(request, _MAX_BODY_BYTES)).decode("utf-8-sig")
        incoming, errors = registry_from_csv(text)
        merged, added, replaced = merge_registries(_load_registry_or_empty(), incoming)
        config.save_registry(registry_dir / "licenses.yaml", merged)
        return RegistryImportResult(registry=merged, errors=errors, added=added, replaced=replaced)

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

    _unsupported = "scheduling is supported on Windows and Linux only"

    @app.get("/api/schedules")
    async def get_schedules() -> list[ScheduleInfo]:
        if not is_supported():
            return []
        try:
            return list_schedules()
        except SchedulerError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedules", status_code=201)
    async def create_schedule_endpoint(spec: ScheduleSpec) -> ScheduleInfo:
        if not is_supported():
            raise HTTPException(status_code=501, detail=_unsupported)
        try:
            return create_schedule(spec, tasks_dir=tasks_dir, working_dir=demo.repo_root())
        except SchedulerError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/schedules/{name}")
    async def delete_schedule_endpoint(name: str) -> dict[str, str]:
        if not is_supported():
            raise HTTPException(status_code=501, detail=_unsupported)
        # Same charset ScheduleSpec enforces at create — the name flows into a
        # schtasks/crontab argument and a log/launcher filename.
        if not is_valid_schedule_name(name):
            raise HTTPException(status_code=400, detail="invalid schedule name")
        try:
            delete_schedule(name, tasks_dir=tasks_dir)
        except SchedulerError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"deleted": name}

    def _workspace_zip() -> bytes:
        return build_workspace_zip(config_dir, registry_dir, reports_dir)

    @app.get("/api/workspace/backups")
    async def list_workspace_backups() -> list[BackupInfo]:
        return list_backups(backups_dir)

    @app.post("/api/workspace/snapshot", status_code=201)
    async def snapshot_workspace() -> BackupInfo:
        return write_snapshot(backups_dir, _workspace_zip(), datetime.now(UTC))

    @app.get("/api/workspace/export")
    async def export_workspace() -> Response:
        filename = snapshot_filename(datetime.now(UTC))
        return Response(
            content=_workspace_zip(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/workspace/backups/{name}")
    async def download_backup(name: str) -> Response:
        try:
            data = read_backup(backups_dir, name)
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    def _restore(data: bytes) -> None:
        # Always snapshot the current state before overwriting, so a restore is
        # itself undoable.
        write_snapshot(backups_dir, _workspace_zip(), datetime.now(UTC))
        try:
            restore_workspace_zip(data, config_dir, registry_dir, reports_dir)
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/workspace/restore/{name}")
    async def restore_backup(name: str) -> dict[str, str]:
        try:
            data = read_backup(backups_dir, name)
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _restore(data)
        return {"restored": name}

    @app.post("/api/workspace/import")
    async def import_workspace(request: Request) -> dict[str, str]:
        _restore(await _read_body(request, _MAX_IMPORT_BODY_BYTES))
        return {"restored": "upload"}

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
