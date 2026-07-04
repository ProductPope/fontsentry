"""End-to-end scan over the offline demo dataset (filesystem transport, no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fontsentry import config, demo
from fontsentry.models import Finding, FindingStatus, RiskBand, RunReport
from fontsentry.scan import run_scan

NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)


async def test_progress_reports_real_phases(repo_root: Path) -> None:
    rules = config.load_rules(repo_root / "config" / "rules.example.yaml")
    registry = config.load_registry(demo.demo_registry_path())
    events: list[tuple[str, int, int]] = []
    client = demo.demo_client()
    try:
        await run_scan(
            demo.demo_targets(),
            demo.demo_settings(),
            rules,
            registry,
            client=client,
            now=NOW,
            progress=lambda phase, cur, total, msg: events.append((phase, cur, total)),
        )
    finally:
        await client.aclose()

    phases = [e[0] for e in events]
    # Phases fire in order and detect runs once per discovered page.
    assert phases.index("discover") < phases.index("detect") < phases.index("score")
    detect_totals = {total for phase, _, total in events if phase == "detect"}
    assert detect_totals and all(t > 0 for t in detect_totals)


@pytest.fixture
async def report(repo_root: Path) -> RunReport:
    rules = config.load_rules(repo_root / "config" / "rules.example.yaml")
    registry = config.load_registry(demo.demo_registry_path())
    client = demo.demo_client()
    try:
        return await run_scan(
            demo.demo_targets(), demo.demo_settings(), rules, registry, client=client, now=NOW
        )
    finally:
        await client.aclose()


@pytest.fixture
def findings(report: RunReport) -> dict[str, Finding]:
    return {f.family: f for f in report.findings}


def _rule_ids(finding: Finding) -> set[str]:
    return {t.id for t in finding.triggered_rules}


async def test_atlas_is_high_risk_cross_domain(findings: dict[str, Finding]) -> None:
    atlas = findings["Atlas Grotesk Private"]
    assert atlas.status is FindingStatus.OPEN
    assert atlas.band is RiskBand.HIGH
    assert atlas.domain_count == 2  # aggregated across both demo domains
    assert {"desktop-format-on-web", "self-host-prohibited", "max-domains-exceeded"} <= _rule_ids(
        atlas
    )


async def test_report_records_duration(report: RunReport) -> None:
    # `>= 0` alone is always true; assert the real contract: a finite float, not
    # None/NaN/inf. (Value can round to 0.0 for a fast demo scan, so no threshold.)
    import math

    assert isinstance(report.duration_seconds, float)
    assert math.isfinite(report.duration_seconds)
    assert report.duration_seconds >= 0


async def test_findings_carry_example_pages(findings: dict[str, Finding]) -> None:
    atlas = findings["Atlas Grotesk Private"]
    assert atlas.example_urls
    assert all(u.startswith("http") for u in atlas.example_urls)
    assert len(atlas.example_urls) <= 5
    assert atlas.page_count >= len(atlas.example_urls)


async def test_harbor_is_suppressed(findings: dict[str, Finding]) -> None:
    harbor = findings["Harbor Serif"]
    assert harbor.status is FindingStatus.RESOLVED
    assert harbor.registry_match is True


async def test_acme_commercial_unregistered(findings: dict[str, Finding]) -> None:
    acme = findings["Acme Display"]
    assert acme.status is FindingStatus.OPEN
    assert {"commercial-no-registry", "missing-copyright"} <= _rule_ids(acme)


async def test_expired_license_surfaces(findings: dict[str, Finding]) -> None:
    expired = findings["Expired Face"]
    assert expired.status is FindingStatus.OPEN
    assert "expired-license" in _rule_ids(expired)


async def test_open_font_not_flagged_commercial(findings: dict[str, Finding]) -> None:
    public = findings["Public Glyphs Sans"]
    # OFL font from a known-free owner must not trigger the commercial rule.
    assert "commercial-no-registry" not in _rule_ids(public)


async def test_domain_view_present(report: RunReport) -> None:
    domains = {d.domain: d for d in report.domains}
    assert set(domains) == {"example-demo.test", "example-shop.test"}

    demo_site = domains["example-demo.test"]
    assert demo_site.is_live is True
    assert demo_site.subdomains == ["blog.example-demo.test"]
    assert demo_site.pages_scanned >= 1
    families = {f.family for f in demo_site.fonts}
    assert {"Atlas Grotesk Private", "Harbor Serif", "Acme Display"} <= families
    # System fallback fonts (e.g. Common Serif) are excluded from the domain font list.
    assert "Common Serif" not in families
    # Acme Display is reused on the subdomain, so it spans two hosts.
    acme = next(f for f in demo_site.fonts if f.family == "Acme Display")
    assert "blog.example-demo.test" in acme.hosts

    # Domain fonts carry embedding + format info.
    atlas = next(f for f in demo_site.fonts if f.family == "Atlas Grotesk Private")
    assert "self_hosted" in atlas.embeddings
    assert "ttf" in atlas.formats

    # ...and the per-host font-file URL(s) it was served from (schema v4).
    assert atlas.assets, "expected per-host asset URLs for a self-hosted font"
    assert {a.host for a in atlas.assets} <= set(atlas.hosts)
    assert all(url for a in atlas.assets for url in a.urls)


async def test_domain_view_per_domain_fonts(report: RunReport) -> None:
    shop = next(d for d in report.domains if d.domain == "example-shop.test")
    families = {f.family for f in shop.fonts}
    assert "Expired Face" in families
    assert "Acme Display" not in families  # only on the other domain
