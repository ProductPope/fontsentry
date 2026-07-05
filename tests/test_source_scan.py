"""Source scan: audit font files in a local tree, offline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fontsentry import config
from fontsentry.models import LicenseVerdict, Registry, RulesConfig
from fontsentry.source_scan import scan_source
from tests.factories import build_test_font

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)


def _rules(repo_root: Path) -> RulesConfig:
    return config.load_rules(repo_root / "config" / "rules.example.yaml")


def test_scan_source_classifies_and_skips(tmp_path: Path, repo_root: Path) -> None:
    fonts = tmp_path / "src" / "assets" / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "commercial.ttf").write_bytes(
        build_test_font(
            family_name="Commercial Sans X",
            manufacturer="Acme Type",
            license_description="Desktop licence only.",
        )
    )
    (fonts / "open.woff2").write_bytes(
        build_test_font(
            family_name="Openish", license_description="SIL Open Font License (OFL)", flavor="woff2"
        )
    )
    (fonts / "restricted.ttf").write_bytes(
        build_test_font(family_name="Locked Down", fs_type=0x0002)
    )

    # A vendored dependency must be skipped, not audited.
    dep = tmp_path / "node_modules" / "pkg"
    dep.mkdir(parents=True)
    (dep / "dep.ttf").write_bytes(build_test_font(family_name="Dep Font"))

    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    verdicts = {f.family: f.license_verdict for f in report.findings}

    assert verdicts["Commercial Sans X"] is LicenseVerdict.NEEDS_CHECK
    assert verdicts["Openish"] is LicenseVerdict.OK
    assert verdicts["Locked Down"] is LicenseVerdict.VIOLATION
    assert "Dep Font" not in verdicts  # node_modules skipped

    # Fonts read from a repo are self-hosted, with the file path recorded.
    commercial = next(f for f in report.findings if f.family == "Commercial Sans X")
    assert commercial.privacy.value == "self_hosted"
    assert any("commercial.ttf" in u for u in commercial.example_urls)


def test_scan_source_empty_tree(tmp_path: Path, repo_root: Path) -> None:
    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    assert report.findings == []


def test_scan_source_ignores_non_font_and_garbage(tmp_path: Path, repo_root: Path) -> None:
    (tmp_path / "readme.md").write_text("# not a font", encoding="utf-8")
    (tmp_path / "broken.woff2").write_bytes(b"not a real font")
    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    assert report.findings == []  # non-font ignored; unparseable font skipped
