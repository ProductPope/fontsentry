"""Shared pytest fixtures. Everything here is offline and filesystem-local."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def config_dir() -> Path:
    return REPO_ROOT / "config"


@pytest.fixture
def registry_dir() -> Path:
    return REPO_ROOT / "registry"
