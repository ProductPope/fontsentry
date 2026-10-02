"""Print the local API's OpenAPI schema as stable JSON.

This is the contract the web UI's TypeScript types are generated from
(``web/openapi.json`` -> ``web/src/lib/api-schema.d.ts``). ``tests/test_openapi.py``
fails when the committed copy no longer matches the code.

    uv run python -m fontsentry.web.openapi > web/openapi.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from fontsentry.web.server import create_app


def schema() -> dict[str, Any]:
    return create_app().openapi()


def render() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    # Bytes, not print(): text-mode stdout would write CRLF on Windows.
    sys.stdout.buffer.write(render().encode("utf-8"))
