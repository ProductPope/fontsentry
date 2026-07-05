"""Export a run report's findings to CSV — one row per font finding.

Flat, spreadsheet-friendly view of the same findings the JSON/HTML reports
carry. List-valued fields are joined with "; ".
"""

from __future__ import annotations

import csv
import io

from fontsentry.models import RunReport

# Cells starting with these are interpreted as formulas by spreadsheet apps.
# Font metadata (family/owner) and URLs are attacker-influenceable, so neutralize
# any such cell with a leading apostrophe (CSV-injection / DDE defense).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in _FORMULA_PREFIXES else text


_HEADER = [
    "family",
    "family_group",
    "owner",
    "license_verdict",
    "license_reason",
    "privacy",
    "needs_action",
    "applied",
    "domain_count",
    "page_count",
    "domains",
    "embeddings",
    "formats",
    "evidence_notes",
    "example_urls",
]


def build_csv(report: RunReport) -> str:
    """Serialize the report's findings to CSV text (header + one row per finding)."""

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    for f in report.findings:
        writer.writerow(
            [
                _safe(f.family),
                _safe(f.family_group or f.family),
                _safe(f.owner or ""),
                f.license_verdict.value,
                _safe(f.license_reason),
                f.privacy.value,
                "yes" if f.needs_action else "no",
                "yes" if f.applied else "no",
                f.domain_count,
                f.page_count,
                _safe("; ".join(f.domains)),
                "; ".join(e.value for e in f.embeddings),
                "; ".join(fmt.value for fmt in f.formats),
                _safe("; ".join(f.evidence_notes)),
                _safe("; ".join(f.example_urls)),
            ]
        )
    return buf.getvalue()
