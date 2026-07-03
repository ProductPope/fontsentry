"""Scan orchestration: crawl every target, detect fonts, score, build a report.

This is the one place the pipeline is wired end to end (crawl -> detect -> risk ->
report). It takes an injected httpx client so the same code path serves both live
scans and the offline demo (which passes a filesystem-backed transport).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from fontsentry.crawl.cache import HttpCache
from fontsentry.crawl.ct import ct_subdomains
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
    discover_ct: bool = False,
    max_pages_per_domain: int | None = None,
) -> RunReport:
    """Crawl, detect, and score; return the run report (font- and domain-centric).

    Runs in two global passes so progress maps to real, user-visible steps:
    discover every domain's pages first, then identify fonts on every page. The
    output is independent of pass order (aggregation and sorting are order-free).

    ``discover_ct`` (opt-in) additionally finds public subdomains via Certificate
    Transparency logs (queries an external service) and crawls each as its own
    host with its own page budget. ``max_pages_per_domain`` overrides the
    per-host page cap for this run.
    """

    started = time.monotonic()
    crawl = settings.crawl
    overrides: dict[str, object] = {}
    if max_pages_per_domain is not None:
        overrides["max_pages_per_domain"] = max_pages_per_domain
    if discover_ct:
        # Subdomains are crawled as separate targets below, so don't also let the
        # apex crawl absorb them into its own budget.
        overrides["discover_subdomains"] = False
    if overrides:
        crawl = crawl.model_copy(update=overrides)

    cache = HttpCache(settings.cache.directory, enabled=settings.cache.enabled)
    robots = RobotsManager(client, crawl.user_agent) if crawl.respect_robots else None
    fetcher = Fetcher(client, crawl, cache=cache, robots=robots)

    # Opt-in CT: expand each target with its public subdomains as SEPARATE targets
    # (each gets its own page budget and its own domain report).
    hosts = list(targets)
    if discover_ct:
        progress("discover", 0, len(hosts), "Finding public subdomains")
        seen = {t.domain for t in targets}
        expanded: list[Target] = []
        for t in targets:
            expanded.append(t)
            for sub in await ct_subdomains(client, t.domain):
                if sub not in seen:
                    seen.add(sub)
                    expanded.append(Target(domain=sub))
        hosts = expanded

    pages_by_domain: dict[str, list[str]] = {}
    detections_by_domain: dict[str, list[DetectedFont]] = {t.domain: [] for t in hosts}

    # Pass 1 — discover pages, per host.
    progress("discover", 0, len(hosts), "Discovering pages")
    for i, target in enumerate(hosts):
        pages_by_domain[target.domain] = await discover_pages(fetcher, target, crawl)
        progress("discover", i + 1, len(hosts), f"Discovered {target.domain}")

    # Pass 2 — identify fonts on every discovered page. Fan out across pages
    # (the Fetcher's semaphore caps in-flight requests and per-host throttling
    # preserves politeness); progress is reported in completion order.
    pages = [(t.domain, page) for t in hosts for page in pages_by_domain[t.domain]]
    detected: list[DetectedFont] = []
    progress("detect", 0, len(pages), "Identifying fonts")

    async def _detect_one(domain: str, page: str) -> tuple[str, list[DetectedFont]]:
        return domain, await detect_page(fetcher, page)

    for done, coro in enumerate(asyncio.as_completed([_detect_one(d, p) for d, p in pages]), 1):
        domain, page_detections = await coro
        detections_by_domain[domain].extend(page_detections)
        detected.extend(page_detections)
        progress("detect", done, len(pages), f"Identifying fonts on {domain}")

    # Pass 3 — aggregate across domains, suppress via registry, and score.
    progress("score", 0, 1, "Scoring and suppression")
    findings = evaluate(detected, rules, registry, now.date())
    domains = _build_domain_reports(hosts, pages_by_domain, detections_by_domain, findings)
    report = build_report(findings, now, domains)
    report.duration_seconds = round(time.monotonic() - started, 1)
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
    discover_ct: bool = False,
    max_pages_per_domain: int | None = None,
) -> tuple[RunReport, Path, Path]:
    """Run a scan and persist the JSON and HTML reports. Returns (report, json, html)."""

    report = await run_scan(
        targets,
        settings,
        rules,
        registry,
        client=client,
        now=now,
        progress=progress,
        discover_ct=discover_ct,
        max_pages_per_domain=max_pages_per_domain,
    )
    progress("report", 0, 1, "Writing report")
    json_path = write_run(report, reports_dir)
    html_path = json_path.with_suffix(".html")
    write_html(report, html_path)
    progress("report", 1, 1, "Report ready")
    return report, json_path, html_path
