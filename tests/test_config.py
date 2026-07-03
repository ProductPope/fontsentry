"""Config loading + model validation. Exercises the committed example files."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fontsentry import config
from fontsentry.config import ConfigError
from fontsentry.models import (
    Registry,
    RegistryEntry,
    RiskBand,
    Settings,
    Target,
    TargetsConfig,
)


def test_targets_save_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "targets.yaml"
    original = TargetsConfig(
        targets=[Target(domain="example.com", subdomain_seeds=["blog.example.com"])]
    )
    config.save_targets(path, original)
    loaded = config.load_targets(path)
    assert loaded.targets[0].domain == "example.com"
    assert loaded.targets[0].subdomain_seeds == ["blog.example.com"]


def test_registry_save_load_preserves_optional_fields(tmp_path: Path) -> None:
    path = tmp_path / "licenses.yaml"
    original = Registry(
        entries=[
            RegistryEntry(
                owner="Meridian Letterworks",
                family="Atlas Grotesk Private",
                license_type="Web, single domain",
                allowed_domains=["example.com"],
                max_domains=1,
                valid_until=date(2027, 12, 31),
                notes="renew before expiry",
            )
        ]
    )
    config.save_registry(path, original)
    entry = config.load_registry(path).entries[0]
    assert entry.max_domains == 1
    assert entry.valid_until == date(2027, 12, 31)
    assert entry.notes == "renew before expiry"


def test_empty_yaml_file_loads_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text("# just a comment\n", encoding="utf-8")
    loaded = config.load_settings(path)
    assert loaded == Settings()  # empty mapping -> all defaults


def test_example_files_load(config_dir: Path, registry_dir: Path) -> None:
    settings = config.load_settings(config_dir / "settings.example.yaml")
    targets = config.load_targets(config_dir / "targets.example.yaml")
    rules = config.load_rules(config_dir / "rules.example.yaml")
    registry = config.load_registry(registry_dir / "licenses.example.yaml")

    assert settings.crawl.max_depth == 2
    assert targets.targets[0].domain == "example.com"
    assert {r.id for r in rules.rules} == {
        "desktop-format-on-web",
        "commercial-no-registry",
        "max-domains-exceeded",
        "self-host-prohibited",
        "paid-cdn-no-registry",
        "missing-copyright",
        "expired-license",
        "paid-tier-in-name",
        "subset-signal",
    }
    assert "Atlas Grotesk Private" in {e.family for e in registry.entries}


def test_resolve_prefers_real_then_example(tmp_path: Path) -> None:
    # Only the example exists -> fall back to it.
    (tmp_path / "settings.example.yaml").write_text("crawl: {max_depth: 1}\n", encoding="utf-8")
    assert config.resolve_config_path(tmp_path, "settings").name == "settings.example.yaml"

    # Real file present -> prefer it.
    (tmp_path / "settings.yaml").write_text("crawl: {max_depth: 1}\n", encoding="utf-8")
    assert config.resolve_config_path(tmp_path, "settings").name == "settings.yaml"


def test_resolve_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        config.resolve_config_path(tmp_path, "settings")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "settings.yaml"
    bad.write_text("crawl: [unbalanced\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        config.load_settings(bad)


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "settings.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        config.load_settings(bad)


def test_unknown_key_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "settings.yaml"
    bad.write_text("crawl:\n  nonsense_key: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        config.load_settings(bad)


def test_domain_scheme_and_trailing_slash_stripped(tmp_path: Path) -> None:
    path = tmp_path / "targets.yaml"
    path.write_text("targets:\n  - domain: 'HTTPS://Example.COM/'\n", encoding="utf-8")
    targets = config.load_targets(path)
    assert targets.targets[0].domain == "example.com"


def test_duplicate_rule_id_rejected(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "scoring:\n"
        "  max_raw: 90\n"
        "  bands: {medium: 30, high: 60}\n"
        "rules:\n"
        "  - {id: dup, weight: 1, confidence: 1, when: {type: subset_signal}}\n"
        "  - {id: dup, weight: 1, confidence: 1, when: {type: subset_signal}}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate rule id"):
        config.load_rules(path)


def test_band_high_below_medium_rejected(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "scoring:\n  max_raw: 90\n  bands: {medium: 60, high: 30}\nrules: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="high"):
        config.load_rules(path)


def test_riskband_values() -> None:
    assert [b.value for b in RiskBand] == ["low", "medium", "high"]
