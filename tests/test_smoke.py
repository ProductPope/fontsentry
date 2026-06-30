"""Baseline smoke test so the suite and CI are wired from the first commit."""

from __future__ import annotations

import fontsentry


def test_version_exposed() -> None:
    assert fontsentry.__version__ == "0.1.0"
