"""Scan orchestration: crawl every target, detect fonts, score, build a report.

This is the one place the pipeline is wired end to end (crawl -> detect -> risk ->
report). It takes an injected httpx client so the same code path serves both live
scans and the offline demo (which passes a filesystem-backed transport).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx

from fontsentry.crawl.cache import HttpCache
from fontsentry.crawl.discovery import discover_pages
from fontsentry.crawl.fetcher import Fetcher
from fontsentry.crawl.robots import RobotsManager
from fontsentry.detect.page import detect_page
from fontsentry.models import DetectedFont, Registry, RulesConfig, RunReport, Settings, Target
from fontsentry.report.html_report import write_html
from fontsentry.report.json_report import build_report, write_run
from fontsentry.risk.engine import evaluate


async def run_scan(
    targets: list[Target],
    settings: Settings,
    rules: RulesConfig,
    registry: Registry,
    *,
    client: httpx.AsyncClient,
    now: datetime,
) -> RunReport:
    """Crawl, detect, and score; return the run report."""

    crawl = settings.crawl
    cache = HttpCache(settings.cache.directory, enabled=settings.cache.enabled)
    robots = RobotsManager(client, crawl.user_agent) if crawl.respect_robots else None
    fetcher = Fetcher(client, crawl, cache=cache, robots=robots)

    detected: list[DetectedFont] = []
    for target in targets:
        pages = await discover_pages(fetcher, target, crawl)
        for page in pages:
            detected.extend(await detect_page(fetcher, page))

    findings = evaluate(detected, rules, registry, now.date())
    return build_report(findings, now)


async def scan_and_write(
    targets: list[Target],
    settings: Settings,
    rules: RulesConfig,
    registry: Registry,
    *,
    client: httpx.AsyncClient,
    now: datetime,
    reports_dir: Path,
) -> tuple[RunReport, Path, Path]:
    """Run a scan and persist the JSON and HTML reports. Returns (report, json, html)."""

    report = await run_scan(targets, settings, rules, registry, client=client, now=now)
    json_path = write_run(report, reports_dir)
    html_path = json_path.with_suffix(".html")
    write_html(report, html_path)
    return report, json_path, html_path
