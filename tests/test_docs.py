"""Documentation-freshness guard.

These tests fail in CI when code and the committed docs drift apart, so the docs
can't silently go stale: a new rule predicate, a new crawl setting, or a new
default rule id must be documented (and the CHANGELOG must carry an Unreleased
section). Matching is by identifier presence, not exact wording — so rephrasing
docs is fine; only *adding a feature without documenting it* fails.
"""

from __future__ import annotations

from pathlib import Path

from fontsentry import config
from fontsentry.models import CrawlSettings
from fontsentry.risk.rules import known_predicate_types


def _read(repo_root: Path, rel: str) -> str:
    return (repo_root / rel).read_text(encoding="utf-8")


def test_every_rule_predicate_is_documented(repo_root: Path) -> None:
    rules_doc = _read(repo_root, "docs/rules.md")
    undocumented = sorted(p for p in known_predicate_types() if p not in rules_doc)
    assert not undocumented, (
        f"condition predicates missing from docs/rules.md: {undocumented}. "
        "Add them to the condition-types table."
    )


def test_every_default_rule_id_is_documented(repo_root: Path) -> None:
    rules = config.load_rules(repo_root / "config" / "rules.example.yaml")
    rules_doc = _read(repo_root, "docs/rules.md")
    undocumented = sorted(r.id for r in rules.rules if r.id not in rules_doc)
    assert not undocumented, (
        f"rule ids in rules.example.yaml missing from docs/rules.md: {undocumented}."
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
