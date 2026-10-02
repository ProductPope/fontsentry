"""Source scan: audit the font files committed to a local repository/directory.

The live crawler only sees fonts a page actually serves in static HTML/CSS, so it
misses fonts wired up by JavaScript on client-rendered (SPA) sites. Reading the
*source* — every font file in a checked-out tree — sidesteps that: it finds the
files regardless of how the app loads them, and judges each one from its own name
table (owner, licence, OS/2 fsType). Deterministic and fully offline.

The same verdict engine classifies the fonts, so a commercial font self-hosted in a
repo lands on the same verdict it would from a live scan — without needing the site
to be reachable or statically rendered.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from fontsentry.detect.fontfile import FontReadError, read_font_metadata
from fontsentry.models import DetectedFont, EmbeddingMethod, Registry, RulesConfig, RunReport
from fontsentry.report.json_report import build_report
from fontsentry.risk.engine import evaluate

_FONT_EXTENSIONS = {".woff2", ".woff", ".ttf", ".otf", ".eot"}

# Directories that never hold first-party source worth auditing (vendored deps,
# build output, VCS internals). Skipped for speed and to avoid false findings.
_SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", ".nuxt", "vendor"}
)

# A font file larger than this is almost certainly not a real web font; skip it so
# a stray large binary can't blow up memory.
_MAX_FONT_BYTES = 20 * 1024 * 1024


def _iter_font_files(root: Path) -> Iterator[Path]:
    # os.walk with in-place pruning: rglob would materialize the whole tree,
    # descend into node_modules/.git anyway (filtering only afterwards), and —
    # on this project's Python floor — follow directory symlinks with no loop
    # protection. followlinks=False also keeps the walk inside `root`.
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() in _FONT_EXTENSIONS and path.is_file():
                yield path


def scan_source(root: Path, rules: RulesConfig, registry: Registry, now: datetime) -> RunReport:
    """Read every font file under ``root``, classify it, and build a run report.

    Fonts are treated as self-hosted (they ship in the repo). There is no domain
    view — the report is font-centric, with each font's source file paths in
    ``example_urls``.
    """

    detected: list[DetectedFont] = []
    for path in _iter_font_files(root):
        try:
            # stat before read: a stray multi-GB file with a font extension must
            # be rejected without ever being loaded into memory.
            if path.stat().st_size > _MAX_FONT_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        try:
            metadata, file_format = read_font_metadata(data)
        except FontReadError:
            continue

        rel = path.relative_to(root).as_posix()
        family = (metadata.family_name or path.stem).strip()
        detected.append(
            DetectedFont(
                family=family,
                embedding=EmbeddingMethod.SELF_HOSTED,
                font_format=file_format,
                source_page=rel,
                font_url=rel,
                metadata=metadata,
                applied=True,
            )
        )

    findings = evaluate(detected, rules, registry, now.date())
    return build_report(findings, now)
