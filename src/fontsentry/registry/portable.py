"""CSV import/export for the owned-license registry (spreadsheet round-trip).

Non-technical operators keep their licensed fonts in a spreadsheet, so the registry
can be exported to / imported from a flat CSV. Nested fields flatten by convention:
``allowed_domains`` is pipe-separated, ``valid_until`` is an ISO date, and empty
cells mean "unset". Import is lenient per-row: a bad row is reported, not fatal.

Proofs are files, not cells — the CSV carries only the ``proof_path`` /
``invoice_path`` filenames; the documents themselves stay under ``registry/proofs/``.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from fontsentry.models import Registry, RegistryEntry

_COLUMNS = [
    "owner",
    "family",
    "license_type",
    "allowed_domains",
    "max_domains",
    "proof_path",
    "invoice_path",
    "valid_until",
    "notes",
]
_REQUIRED = ("owner", "family", "license_type")
_DOMAIN_SEP = "|"


def registry_to_csv(registry: Registry) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for e in registry.entries:
        writer.writerow(
            {
                "owner": e.owner,
                "family": e.family,
                "license_type": e.license_type,
                "allowed_domains": _DOMAIN_SEP.join(e.allowed_domains),
                "max_domains": "" if e.max_domains is None else e.max_domains,
                "proof_path": e.proof_path or "",
                "invoice_path": e.invoice_path or "",
                "valid_until": e.valid_until.isoformat() if e.valid_until else "",
                "notes": e.notes or "",
            }
        )
    return out.getvalue()


def _describe(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
    return str(exc)


def _row_to_entry(row: dict[str, str | None]) -> RegistryEntry:
    def field(key: str) -> str:
        return (row.get(key) or "").strip()

    domains = [d.strip() for d in field("allowed_domains").split(_DOMAIN_SEP) if d.strip()]
    max_domains = field("max_domains")
    valid_until = field("valid_until")
    proof = field("proof_path")
    invoice = field("invoice_path")
    return RegistryEntry(
        owner=field("owner"),
        family=field("family"),
        license_type=field("license_type"),
        allowed_domains=domains,
        max_domains=int(max_domains) if max_domains else None,
        proof_path=Path(proof) if proof else None,
        invoice_path=Path(invoice) if invoice else None,
        valid_until=date.fromisoformat(valid_until) if valid_until else None,
        notes=field("notes") or None,
    )


def registry_from_csv(text: str) -> tuple[Registry, list[str]]:
    """Parse CSV into a Registry, returning (entries, per-row errors).

    A header with the required columns is mandatory; missing them fails fast. Fully
    blank rows are skipped. Any row that won't validate is collected as an error
    (``row N: reason``) and left out — the caller decides what to do with the rest.
    """

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in _REQUIRED if c not in header]
    if missing:
        return Registry(), [f"missing required column(s): {', '.join(missing)}"]

    entries: list[RegistryEntry] = []
    errors: list[str] = []
    for line_no, row in enumerate(reader, start=2):  # row 1 is the header
        if not any((value or "").strip() for value in row.values()):
            continue  # blank line
        try:
            entries.append(_row_to_entry(row))
        except (ValidationError, ValueError) as exc:
            errors.append(f"row {line_no}: {_describe(exc)}")
    return Registry(entries=entries), errors
