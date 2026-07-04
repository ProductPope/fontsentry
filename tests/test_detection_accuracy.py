"""Detection accuracy on the controlled demo corpus.

The demo sites are synthetic fixtures, so we know exactly which web fonts they
serve — a deterministic ground truth. This measures the tool's core, proven claim
(it surfaces embedded web fonts) as precision/recall, offline and reproducibly.
Extend with hand-verified real pages for external validation (see methodology.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fontsentry import config, demo
from fontsentry.models import EmbeddingMethod, Finding, RunReport
from fontsentry.scan import run_scan

NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)

# Ground truth from the demo fixtures (demo/sites/**): fonts actually delivered via
# @font-face, and the fallback families only ever referenced (never embedded).
EMBEDDED_FONTS = {
    "Acme Display",
    "Atlas Grotesk Private",
    "Harbor Serif",
    "Public Glyphs Sans",
    "Expired Face",
}
SYSTEM_FALLBACKS = {"Common Sans", "Common Serif"}


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


def _is_embedded(f: Finding) -> bool:
    return any(e is not EmbeddingMethod.SYSTEM for e in f.embeddings)


async def test_embedded_font_detection_precision_recall(report: RunReport) -> None:
    detected = {f.family for f in report.findings if _is_embedded(f)}
    tp = detected & EMBEDDED_FONTS
    precision = len(tp) / len(detected) if detected else 0.0
    recall = len(tp) / len(EMBEDDED_FONTS)
    # On the controlled corpus the detector is exact: no false fonts, none missed.
    assert precision == 1.0, f"false detections: {sorted(detected - EMBEDDED_FONTS)}"
    assert recall == 1.0, f"missed fonts: {sorted(EMBEDDED_FONTS - detected)}"


async def test_fallbacks_classified_as_system_not_embedded(report: RunReport) -> None:
    system = {f.family for f in report.findings if not _is_embedded(f)}
    # Fallback families are surfaced but correctly marked system (not embedded),
    # so they never inflate the embedded-font precision above.
    assert system >= SYSTEM_FALLBACKS
    assert not (EMBEDDED_FONTS & system)
