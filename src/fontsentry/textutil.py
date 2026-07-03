"""Decode fetched HTML/CSS bytes using the HTTP charset when given.

Pages aren't always UTF-8; a legacy latin-1 / Shift-JIS page decoded as UTF-8
yields mojibake family names (and a corrupted `@font-face` family breaks registry
matching). We honor the Content-Type charset, then fall back to UTF-8.
"""

from __future__ import annotations

import re

_CHARSET = re.compile(r"charset=([^;\s]+)", re.IGNORECASE)


def decode_text(content: bytes, content_type: str) -> str:
    match = _CHARSET.search(content_type or "")
    if match:
        codec = match.group(1).strip().strip("\"'")
        try:
            return content.decode(codec)
        except (LookupError, UnicodeDecodeError):
            pass
    return content.decode("utf-8", errors="replace")
