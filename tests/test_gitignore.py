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
    "config/anything-else.yaml",
    "registry/licenses.yaml",
    "registry/proofs/secret-invoice.pdf",
    "reports/fontsentry-20260101T000000Z.report.json",
    "reports/summary.html",
    "backups/fontsentry-workspace-20260101T000000Z.zip",
    ".cache/fetched-page.html",
    ".fontsentry-cache/fetched-body.bin",
    ".fontsentry-tasks/nightly-audit.bat",
    "validation/labels.yaml",
    "validation/labels-old.yaml",
    "validation/result.md",
    "external/some-private-audit.csv",
    ".env",
    ".env.production",
]


@pytest.mark.parametrize("path", _MUST_IGNORE)
def test_sensitive_path_is_gitignored(path: str) -> None:
    result = _git("check-ignore", path)
    assert result.returncode == 0, f"{path} is NOT gitignored — user data could be committed"


# Real user data that must never be tracked, whatever the directory. Mirrors the
# sensitive classes of .gitignore (not the build/tooling noise, which leaks nothing).
_FORBIDDEN = re.compile(
    r"^config/[^/]+\.ya?ml$"  # any real config (only *.example.yaml is committed)
    r"|(^|/)(targets|settings|rules)\.ya?ml$"
    r"|(^|/)licenses\.ya?ml$"
    r"|\.report\.json$"
    r"|^reports/"  # every generated report artifact (html/csv/json)
    r"|^out/"
    r"|^backups/"
    r"|^\.cache/"  # crawl caches hold fetched content from the user's targets
    r"|^\.fontsentry-cache/"
    r"|^\.fontsentry-tasks/"  # generated launchers embed local paths
    r"|^external/"
    r"|^validation/"  # ground truth + results (only the example + README are committed)
    r"|^registry/proofs/"
    r"|^\.env(\.|$)"  # .env and every .env.* variant
)
# Committed on purpose: templates, the synthetic demo corpus (top-level demo/ only —
# a demo/ directory elsewhere, e.g. reports/demo/, is NOT exempt), placeholders.
_ALLOWED = re.compile(
    r"\.example\."
    r"|^demo/"
    r"|\.gitkeep$"
    r"|^registry/proofs/example-proof\.pdf$"
    r"|^validation/README\.md$"
    r"|(^|/)\.env\.example$"
)


def test_no_user_data_is_tracked() -> None:
    tracked = _git("ls-files").stdout.splitlines()
    leaked = [f for f in tracked if _FORBIDDEN.search(f) and not _ALLOWED.search(f)]
    assert leaked == [], f"real user data is tracked in git (must be gitignored): {leaked}"


# Self-test of the guard itself: every class of leak it exists to catch, and every
# committed-on-purpose exception. A regex edit that reopens a hole fails here.
_LEAK_CASES = [
    "config/customer-rules.yaml",
    "somewhere/targets.yaml",
    "reports/summary.html",
    "reports/demo/fontsentry-x.report.json",  # demo/ exemption must not apply here
    "backups/snapshot.zip",
    ".cache/fetched-page.html",
    ".fontsentry-cache/fetched-body.bin",
    ".fontsentry-tasks/nightly-audit.bat",
    "external/private-audit.csv",
    "validation/labels-old.yaml",
    "validation/result-2.md",
    "registry/proofs/invoice.pdf",
    ".env",
    ".env.production",
]
_COMMITTED_EXCEPTIONS = [
    "config/rules.example.yaml",
    "demo/registry/licenses.yaml",
    "validation/labels.example.yaml",
    "validation/README.md",
    "registry/proofs/.gitkeep",
    "registry/proofs/example-proof.pdf",
    ".env.example",
]


@pytest.mark.parametrize("path", _LEAK_CASES)
def test_guard_catches_leak_class(path: str) -> None:
    assert _FORBIDDEN.search(path), f"guard no longer recognizes {path} as sensitive"
    assert not _ALLOWED.search(path), f"guard exempts {path}, which is real user data"


@pytest.mark.parametrize("path", _COMMITTED_EXCEPTIONS)
def test_guard_permits_committed_exception(path: str) -> None:
    assert not (_FORBIDDEN.search(path) and not _ALLOWED.search(path)), (
        f"guard would flag the deliberately committed {path}"
    )
