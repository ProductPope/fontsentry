"""Source scan: audit font files in a local tree, offline."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fontsentry import config, source_scan
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


def test_skip_dirs_are_never_entered(
    tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: rglob enumerated the whole tree (100k+ entries in node_modules)
    # and filtered afterwards; the walk must prune skip-dirs before descending.
    dep = tmp_path / "node_modules" / "pkg"
    dep.mkdir(parents=True)
    (dep / "dep.ttf").write_bytes(build_test_font(family_name="Dep Font"))

    visited: list[str] = []
    original_stat = Path.stat

    def spying_stat(self: Path, **kw: Any) -> os.stat_result:
        visited.append(str(self))
        return original_stat(self, **kw)

    monkeypatch.setattr(Path, "stat", spying_stat)
    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    assert report.findings == []
    assert not any("node_modules" in v for v in visited)


def test_oversized_file_skipped_without_reading(
    tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the size cap used to apply AFTER read_bytes(), so a stray
    # multi-GB file with a font extension was loaded into memory before rejection.
    monkeypatch.setattr(source_scan, "_MAX_FONT_BYTES", 10)
    big = tmp_path / "big.ttf"
    big.write_bytes(b"x" * 100)

    reads: list[Path] = []
    original_read = Path.read_bytes

    def spying_read(self: Path) -> bytes:
        reads.append(self)
        return original_read(self)

    monkeypatch.setattr(Path, "read_bytes", spying_read)
    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    assert report.findings == []
    assert big not in reads


def test_symlink_loop_terminates(tmp_path: Path, repo_root: Path) -> None:
    # A `loop -> ..` directory symlink used to recurse (rglob follows directory
    # symlinks on this Python floor); the walk must not follow links at all.
    (tmp_path / "real.ttf").write_bytes(build_test_font(family_name="Real Font"))
    try:
        (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks requires privileges on this platform")
    report = scan_source(tmp_path, _rules(repo_root), Registry(), NOW)
    assert [f.family for f in report.findings] == ["Real Font"]  # once, and it returned
