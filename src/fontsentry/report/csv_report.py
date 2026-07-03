"""Export a run report's findings to CSV — one row per font finding.

Flat, spreadsheet-friendly view of the same findings the JSON/HTML reports
carry. List-valued fields are joined with "; ".
"""

from __future__ import annotations

import csv
import io

from fontsentry.models import RunReport

_HEADER = [
    "family",
    "owner",
    "band",
    "score",
    "status",
    "privacy",
    "applied",
    "domain_count",
    "page_count",
    "domains",
    "embeddings",
    "formats",
    "rules",
    "example_urls",
    "suppression_reason",
]


def build_csv(report: RunReport) -> str:
    """Serialize the report's findings to CSV text (header + one row per finding)."""

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    for f in report.findings:
        writer.writerow(
            [
                f.family,
                f.owner or "",
                f.band.value,
                f.score,
                f.status.value,
                f.privacy.value,
                "yes" if f.applied else "no",
                f.domain_count,
                f.page_count,
                "; ".join(f.domains),
                "; ".join(e.value for e in f.embeddings),
                "; ".join(fmt.value for fmt in f.formats),
                "; ".join(t.id for t in f.triggered_rules),
                "; ".join(f.example_urls),
                f.suppression_reason or "",
            ]
        )
    return buf.getvalue()
