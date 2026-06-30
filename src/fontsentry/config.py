"""Load and validate YAML config into pydantic models.

The tool loads the *real* (gitignored) config files. When a real file is absent,
:func:`resolve_config_path` falls back to the committed ``*.example.yaml`` template
so the demo dataset and a fresh clone work out of the box.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from fontsentry.models import Registry, RulesConfig, Settings, TargetsConfig


class ConfigError(Exception):
    """Raised when a config file is missing or fails validation."""


def resolve_config_path(directory: Path, stem: str) -> Path:
    """Return ``<stem>.yaml`` if it exists, else the ``<stem>.example.yaml`` fallback.

    Raises :class:`ConfigError` if neither exists.
    """

    real = directory / f"{stem}.yaml"
    if real.exists():
        return real
    example = directory / f"{stem}.example.yaml"
    if example.exists():
        return example
    raise ConfigError(
        f"no config found: neither {real} nor {example} exists. Copy the example file and edit it."
    )


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        kind = type(raw).__name__
        raise ConfigError(f"expected a mapping at the top level of {path}, got {kind}")
    return raw


def _load_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    data = _load_yaml_mapping(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid config in {path}:\n{exc}") from exc


def load_settings(path: Path) -> Settings:
    return _load_model(path, Settings)


def load_targets(path: Path) -> TargetsConfig:
    return _load_model(path, TargetsConfig)


def load_rules(path: Path) -> RulesConfig:
    return _load_model(path, RulesConfig)


def load_registry(path: Path) -> Registry:
    return _load_model(path, Registry)
