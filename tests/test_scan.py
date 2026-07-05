"""End-to-end scan over the offline demo dataset (filesystem transport, no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fontsentry import config, demo
from fontsentry.models import Finding, LicenseVerdict, RunReport
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


def _notes(finding: Finding) -> str:
    return " ".join(finding.evidence_notes)


async def test_atlas_is_violation_cross_domain(findings: dict[str, Finding]) -> None:
    atlas = findings["Atlas Grotesk Private"]
    assert atlas.license_verdict is LicenseVerdict.VIOLATION
    assert atlas.domain_count == 2  # aggregated across both demo domains


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


async def test_harbor_is_covered(findings: dict[str, Finding]) -> None:
    harbor = findings["Harbor Serif"]
    assert harbor.license_verdict is LicenseVerdict.OK
    assert harbor.registry_match is True
    assert "covered by your license" in harbor.license_reason


async def test_acme_needs_check_with_evidence(findings: dict[str, Finding]) -> None:
    acme = findings["Acme Display"]
    assert acme.license_verdict is LicenseVerdict.NEEDS_CHECK
    assert "no license or copyright" in _notes(acme)
    assert "desktop font format" in _notes(acme)


async def test_expired_license_is_violation(findings: dict[str, Finding]) -> None:
    expired = findings["Expired Face"]
    assert expired.license_verdict is LicenseVerdict.VIOLATION
    assert "expired" in expired.license_reason


async def test_open_font_is_ok(findings: dict[str, Finding]) -> None:
    public = findings["Public Glyphs Sans"]
    # OFL font from a known-free owner is provably open -> OK, not NEEDS_CHECK.
    assert public.license_verdict is LicenseVerdict.OK


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
