"""Response/request models for the web API (thin DTOs over the domain models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from fontsentry.models import RunSummary


class RunMeta(BaseModel):
    id: str
    generated_at: datetime
    summary: RunSummary


class FirstSeen(BaseModel):
    domain: str
    family: str
    first_seen: datetime


class KnownFont(BaseModel):
    family: str
    owner: str | None = None
    source: str  # "detected" (seen in an audit) | "catalog" (bundled suggestion)


class ScanRequest(BaseModel):
    mode: str = "demo"  # "demo" | "real"
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
