"""Documentation-freshness guard.

These tests fail in CI when code and the committed docs drift apart, so the docs
can't silently go stale: a new classification config key or a new crawl setting
must be documented (and the CHANGELOG must carry an Unreleased section).
Matching is by identifier presence, not exact wording — so rephrasing docs is
fine; only *adding a feature without documenting it* fails.
"""

from __future__ import annotations

from pathlib import Path

from fontsentry.models import CrawlSettings, RulesConfig


def _read(repo_root: Path, rel: str) -> str:
    return (repo_root / rel).read_text(encoding="utf-8")


def test_every_classification_key_is_documented(repo_root: Path) -> None:
    rules_doc = _read(repo_root, "docs/rules.md")
    undocumented = sorted(f for f in RulesConfig.model_fields if f not in rules_doc)
    assert not undocumented, (
        f"classification config keys missing from docs/rules.md: {undocumented}. "
        "Document them in the classification reference."
    )


def test_every_crawl_setting_is_documented(repo_root: Path) -> None:
    settings_doc = _read(repo_root, "config/settings.example.yaml")
    undocumented = sorted(f for f in CrawlSettings.model_fields if f not in settings_doc)
    assert not undocumented, (
        f"CrawlSettings fields missing from config/settings.example.yaml: {undocumented}."
    )


def test_changelog_has_unreleased_section(repo_root: Path) -> None:
    changelog = _read(repo_root, "CHANGELOG.md")
    assert "## [Unreleased]" in changelog, (
        "CHANGELOG.md must keep an '## [Unreleased]' section for pending changes."
    )
