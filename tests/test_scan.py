"""End-to-end scan over the offline demo dataset (filesystem transport, no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fontsentry import config, demo
from fontsentry.models import Finding, FindingStatus, RiskBand
from fontsentry.scan import run_scan

NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
async def findings(repo_root: Path) -> dict[str, Finding]:
    rules = config.load_rules(repo_root / "config" / "rules.example.yaml")
    registry = config.load_registry(demo.demo_registry_path())
    client = demo.demo_client()
    try:
        report = await run_scan(
            demo.demo_targets(), demo.demo_settings(), rules, registry, client=client, now=NOW
        )
    finally:
        await client.aclose()
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
    # OFL font from a known-free foundry must not trigger the commercial rule.
    assert "commercial-no-registry" not in _rule_ids(public)
