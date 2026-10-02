"""Response/request models for the web API (thin DTOs over the domain models)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from fontsentry.models import Registry, RunSummary
from fontsentry.web.jobs import ScanMode


class RunMeta(BaseModel):
    id: str
    generated_at: datetime
    summary: RunSummary


class RegistryImportResult(BaseModel):
    """Result of a registry import: the merged registry, per-row errors (CSV only),
    and how the merge changed what was already there — replacements are reported
    because an import can silently *loosen* an entry (e.g. drop its expiry)."""

    registry: Registry
    errors: list[str] = Field(default_factory=list)
    added: int = 0
    replaced: int = 0


class FirstSeen(BaseModel):
    domain: str
    family: str
    first_seen: datetime


class KnownFont(BaseModel):
    family: str
    owner: str | None = None
    # "detected" (seen in an audit) | "catalog" (bundled suggestion)
    source: Literal["detected", "catalog"]


class ScanRequest(BaseModel):
    mode: ScanMode = "demo"
    # Opt-in: also find public subdomains via Certificate Transparency logs and
    # crawl each as its own host (queries an external service; real mode only).
    discover_subdomains: bool = False
    # Per-scan override of the per-host page cap.
    max_pages_per_domain: int | None = Field(default=None, ge=1)


class ScanEstimate(BaseModel):
    eta_seconds: float | None  # None when there's no timed history to estimate from
    based_on_runs: int


class ScanStarted(BaseModel):
    job_id: str
