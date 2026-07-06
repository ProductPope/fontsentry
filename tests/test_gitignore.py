"""Repo-hygiene guard: a user's real data must never be committable.

FontSentry stores config, licenses, proofs, reports, backups, and any local-only
`external/` material *inside* the git repo, kept out of commits by `.gitignore`.
That invariant is load-bearing (the data is private and must never reach GitHub),
so it is checked here: a loosened ignore rule or an accidental `git add` turns CI
red instead of silently leaking.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=_REPO, capture_output=True, text=True, check=False)


def _is_git_checkout() -> bool:
    result = _git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


pytestmark = pytest.mark.skipif(not _is_git_checkout(), reason="not a git checkout")


# Representative sensitive paths that MUST be gitignored (they need not exist —
# check-ignore matches patterns, not files).
_MUST_IGNORE = [
    "config/targets.yaml",
    "config/settings.yaml",
    "config/rules.yaml",
    "registry/licenses.yaml",
    "registry/proofs/secret-invoice.pdf",
    "reports/fontsentry-20260101T000000Z.report.json",
    "backups/fontsentry-workspace-20260101T000000Z.zip",
    "validation/labels.yaml",
    "validation/result.md",
    "external/some-private-audit.csv",
    ".env",
]


@pytest.mark.parametrize("path", _MUST_IGNORE)
def test_sensitive_path_is_gitignored(path: str) -> None:
    result = _git("check-ignore", path)
    assert result.returncode == 0, f"{path} is NOT gitignored — user data could be committed"


# Real user data that must never be tracked, whatever the directory.
_FORBIDDEN = re.compile(
    r"(^|/)(targets|settings|rules)\.yaml$"
    r"|(^|/)licenses\.yaml$"
    r"|\.report\.json$"
    r"|^backups/"
    r"|^external/"
    r"|^validation/(labels|result)\.(yaml|md)$"
    r"|^registry/proofs/"
    r"|^\.env$"
)
# Committed on purpose: templates, the synthetic demo dataset, placeholders.
_ALLOWED = re.compile(
    r"\.example\."
    r"|(^|/)demo/"
    r"|\.gitkeep$"
    r"|registry/proofs/example-proof\.pdf$"
    r"|(^|/)\.env\.example$"
)


def test_no_user_data_is_tracked() -> None:
    tracked = _git("ls-files").stdout.splitlines()
    leaked = [f for f in tracked if _FORBIDDEN.search(f) and not _ALLOWED.search(f)]
    assert leaked == [], f"real user data is tracked in git (must be gitignored): {leaked}"
