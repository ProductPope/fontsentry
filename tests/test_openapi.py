"""The committed API contract (web/openapi.json) must match the code.

The web UI's TypeScript types are generated from that file, so a backend model
change that isn't regenerated would let the UI and the server silently disagree.
"""

from __future__ import annotations

import json
from pathlib import Path

from fontsentry.web.openapi import schema


def test_committed_openapi_matches_code(repo_root: Path) -> None:
    # Compared as data, not text, so a CRLF checkout doesn't matter.
    committed = json.loads((repo_root / "web" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == schema(), (
        "web/openapi.json is stale. Regenerate it and the UI types:\n"
        "  uv run python -m fontsentry.web.openapi > web/openapi.json\n"
        "  cd web && npm run gen:api"
    )
