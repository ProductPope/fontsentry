"""Scan orchestration: crawl every target, detect fonts, score, build a report.

This is the one place the pipeline is wired end to end (crawl -> detect -> risk ->
report). It takes an injected httpx client so the same code path serves both live
scans and the offline demo (which passes a filesystem-backed transport).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from fontsentry.crawl.cache import HttpCache
from fontsentry.crawl.discovery import discover_pages
from fontsentry.crawl.fetcher import Fetcher
from fontsentry.crawl.robots import RobotsManager
from fontsentry.detect.page import detect_page
from fontsentry.models import (
    DetectedFont,
    DomainFont,
    DomainReport,
    EmbeddingMethod,
    Finding,
    FindingStatus,
    Registry,
    RiskBand,
    RulesConfig,
    RunReport,
    Settings,
    Target,
)
from fontsentry.report.html_report import write_html
from fontsentry.report.json_report import build_report, write_run
from fontsentry.risk.engine import evaluate


def _host(url: str) -> str:
    return urlsplit(url).hostname or url


def _build_domain_reports(
    targets: list[Target],
    pages_by_domain: dict[str, list[str]],
    detections_by_domain: dict[str, list[DetectedFont]],
    findings: list[Finding],
) -> list[DomainReport]:
    """Pivot the scan into a per-domain view: hosts, subdomains, and fonts used."""

    finding_by_family = {f.family.strip().lower(): f for f in findings}
    reports: list[DomainReport] = []

    for target in targets:
        domain = target.domain
        pages = pages_by_domain.get(domain, [])
        live_hosts = sorted({_host(p) for p in pages})
        subdomains = [h for h in live_hosts if h != domain and h.endswith("." + domain)]

        # family -> hosts it was seen on (real web fonts only, not system fallbacks)
        family_hosts: dict[str, set[str]] = {}
        for det in detections_by_domain.get(domain, []):
            if det.embedding is EmbeddingMethod.SYSTEM:
                continue
            family_hosts.setdefault(det.family, set()).add(_host(det.source_page))

        fonts: list[DomainFont] = []
        for family, hosts in sorted(family_hosts.items(), key=lambda kv: kv[0].lower()):
            finding = finding_by_family.get(family.strip().lower())
            fonts.append(
                DomainFont(
                    family=family,
                    foundry=finding.foundry if finding else None,
                    band=finding.band if finding else RiskBand.LOW,
                    status=finding.status if finding else FindingStatus.OPEN,
                    hosts=sorted(hosts),
                )
            )

        reports.append(
            DomainReport(
                domain=domain,
                is_live=bool(live_hosts),
                pages_scanned=len(pages),
                live_hosts=live_hosts,
                subdomains=subdomains,
                fonts=fonts,
            )
        )

    return reports


async def run_scan(
    targets: list[Target],
    settings: Settings,
    rules: RulesConfig,
    registry: Registry,
    *,
    client: httpx.AsyncClient,
    now: datetime,
) -> RunReport:
    """Crawl, detect, and score; return the run report (font- and domain-centric)."""

    crawl = settings.crawl
    cache = HttpCache(settings.cache.directory, enabled=settings.cache.enabled)
    robots = RobotsManager(client, crawl.user_agent) if crawl.respect_robots else None
    fetcher = Fetcher(client, crawl, cache=cache, robots=robots)

    detected: list[DetectedFont] = []
    pages_by_domain: dict[str, list[str]] = {}
    detections_by_domain: dict[str, list[DetectedFont]] = {}

    for target in targets:
        pages = await discover_pages(fetcher, target, crawl)
        target_detections: list[DetectedFont] = []
        for page in pages:
            target_detections.extend(await detect_page(fetcher, page))
        detected.extend(target_detections)
        pages_by_domain[target.domain] = pages
        detections_by_domain[target.domain] = target_detections

    findings = evaluate(detected, rules, registry, now.date())
    domains = _build_domain_reports(targets, pages_by_domain, detections_by_domain, findings)
    return build_report(findings, now, domains)


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
