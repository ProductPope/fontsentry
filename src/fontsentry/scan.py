"""Scan orchestration: crawl every target, detect fonts, score, build a report.

This is the one place the pipeline is wired end to end (crawl -> detect -> risk ->
report). It takes an injected httpx client so the same code path serves both live
scans and the offline demo (which passes a filesystem-backed transport).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
    FontFormat,
    HostAsset,
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

# (phase, current, total, message) — total 0 means indeterminate. Called
# synchronously from the scan loop; keep it cheap (it only mutates job state).
ProgressFn = Callable[[str, int, int, str], None]


def _noop_progress(phase: str, current: int, total: int, message: str) -> None:
    return None


def _host(url: str) -> str:
    return urlsplit(url).hostname or url


@dataclass
class _DomainUsage:
    hosts: set[str] = field(default_factory=set)
    embeddings: set[EmbeddingMethod] = field(default_factory=set)
    formats: set[FontFormat] = field(default_factory=set)
    assets: dict[str, set[str]] = field(default_factory=dict)  # host -> font-file URLs


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

        # family -> how it was embedded on this domain (real web fonts, not fallbacks)
        usage: dict[str, _DomainUsage] = {}
        for det in detections_by_domain.get(domain, []):
            if det.embedding is EmbeddingMethod.SYSTEM:
                continue
            host = _host(det.source_page)
            entry = usage.setdefault(det.family, _DomainUsage())
            entry.hosts.add(host)
            entry.embeddings.add(det.embedding)
            entry.formats.add(det.font_format)
            if det.font_url:
                entry.assets.setdefault(host, set()).add(det.font_url)

        fonts: list[DomainFont] = []
        for family, used in sorted(usage.items(), key=lambda kv: kv[0].lower()):
            finding = finding_by_family.get(family.strip().lower())
            fonts.append(
                DomainFont(
                    family=family,
                    owner=finding.owner if finding else None,
                    band=finding.band if finding else RiskBand.LOW,
                    status=finding.status if finding else FindingStatus.OPEN,
                    embeddings=sorted(used.embeddings, key=lambda e: e.value),
                    formats=sorted(used.formats, key=lambda f: f.value),
                    hosts=sorted(used.hosts),
                    assets=[
                        HostAsset(host=h, urls=sorted(urls))
                        for h, urls in sorted(used.assets.items())
                    ],
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
    progress: ProgressFn = _noop_progress,
) -> RunReport:
    """Crawl, detect, and score; return the run report (font- and domain-centric).

    Runs in two global passes so progress maps to real, user-visible steps:
    discover every domain's pages first, then identify fonts on every page. The
    output is independent of pass order (aggregation and sorting are order-free).
    """

    crawl = settings.crawl
    cache = HttpCache(settings.cache.directory, enabled=settings.cache.enabled)
    robots = RobotsManager(client, crawl.user_agent) if crawl.respect_robots else None
    fetcher = Fetcher(client, crawl, cache=cache, robots=robots)

    pages_by_domain: dict[str, list[str]] = {}
    detections_by_domain: dict[str, list[DetectedFont]] = {t.domain: [] for t in targets}

    # Pass 1 — discover subdomains and pages, per domain.
    progress("discover", 0, len(targets), "Discovering subdomains and pages")
    for i, target in enumerate(targets):
        pages_by_domain[target.domain] = await discover_pages(fetcher, target, crawl)
        progress("discover", i + 1, len(targets), f"Discovered {target.domain}")

    # Pass 2 — identify fonts on every discovered page.
    pages = [(target.domain, page) for target in targets for page in pages_by_domain[target.domain]]
    detected: list[DetectedFont] = []
    progress("detect", 0, len(pages), "Identifying fonts")
    for j, (domain, page) in enumerate(pages):
        page_detections = await detect_page(fetcher, page)
        detections_by_domain[domain].extend(page_detections)
        detected.extend(page_detections)
        progress("detect", j + 1, len(pages), f"Identifying fonts on {domain}")

    # Pass 3 — aggregate across domains, suppress via registry, and score.
    progress("score", 0, 1, "Scoring and suppression")
    findings = evaluate(detected, rules, registry, now.date())
    domains = _build_domain_reports(targets, pages_by_domain, detections_by_domain, findings)
    report = build_report(findings, now, domains)
    progress("score", 1, 1, "Scoring complete")
    return report


async def scan_and_write(
    targets: list[Target],
    settings: Settings,
    rules: RulesConfig,
    registry: Registry,
    *,
    client: httpx.AsyncClient,
    now: datetime,
    reports_dir: Path,
    progress: ProgressFn = _noop_progress,
) -> tuple[RunReport, Path, Path]:
    """Run a scan and persist the JSON and HTML reports. Returns (report, json, html)."""

    report = await run_scan(
        targets, settings, rules, registry, client=client, now=now, progress=progress
    )
    progress("report", 0, 1, "Writing report")
    json_path = write_run(report, reports_dir)
    html_path = json_path.with_suffix(".html")
    write_html(report, html_path)
    progress("report", 1, 1, "Report ready")
    return report, json_path, html_path
