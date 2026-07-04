"""The background scan job: load config, run the pipeline, record job status.

Kept out of the HTTP layer — this is orchestration, not request handling. Config
loading is inside the try so a bad config marks the job as error (and the client
is closed) instead of leaving a zombie "running" job.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from fontsentry import config, demo
from fontsentry.scan import scan_and_write
from fontsentry.web.jobs import JobManager
from fontsentry.web.paths import _reports_for


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
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.crawl.request_timeout, connect=10.0),
                limits=httpx.Limits(max_connections=settings.crawl.concurrency * 2),
            )

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
