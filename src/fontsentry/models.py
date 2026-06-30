"""Pydantic domain models shared across the package.

Config-side models (settings, targets, rules, registry) live here. Runtime models
produced during a scan (detected fonts, findings) are added by the detect/risk
phases. Enums are shared by everything, so they live here too.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmbeddingMethod(StrEnum):
    """How a font is delivered to the page."""

    SELF_HOSTED = "self_hosted"
    GOOGLE_FONTS = "google_fonts"
    ADOBE_FONTS = "adobe_fonts"
    MONOTYPE = "monotype"
    OTHER_CDN = "other_cdn"
    SYSTEM = "system"


class FontFormat(StrEnum):
    """Web font file format."""

    WOFF2 = "woff2"
    WOFF = "woff"
    TTF = "ttf"
    OTF = "otf"
    EOT = "eot"
    UNKNOWN = "unknown"


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


class CrawlSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_depth: int = Field(default=2, ge=0, description="Link-following depth from each homepage.")
    max_pages_per_domain: int = Field(default=50, ge=1)
    concurrency: int = Field(default=8, ge=1, description="Max concurrent in-flight requests.")
    per_host_rate_limit: float = Field(
        default=2.0, gt=0, description="Max requests per second per host."
    )
    request_timeout: float = Field(default=15.0, gt=0, description="Per-request timeout, seconds.")
    user_agent: str = Field(
        default="FontSentry/0.1 (+https://github.com/fontsentry/fontsentry)",
        min_length=1,
    )
    respect_robots: bool = True
    discover_subdomains: bool = Field(
        default=True, description="Passive subdomain discovery (sitemap, links, seeds) only."
    )


class CacheSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    directory: Path = Path(".fontsentry-cache")


class PlaywrightSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="JS-injected-font fallback renderer. Off by default; requires the "
        "'browser' extra.",
    )


class OutputSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports_dir: Path = Path("reports")


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crawl: CrawlSettings = CrawlSettings()
    cache: CacheSettings = CacheSettings()
    playwright: PlaywrightSettings = PlaywrightSettings()
    output: OutputSettings = OutputSettings()


# --------------------------------------------------------------------------- #
# Targets
# --------------------------------------------------------------------------- #


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    subdomain_seeds: list[str] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def _strip_scheme(cls, value: str) -> str:
        value = value.strip().lower()
        for prefix in ("https://", "http://"):
            if value.startswith(prefix):
                value = value[len(prefix) :]
        return value.rstrip("/")


class TargetsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[Target] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Risk rules
# --------------------------------------------------------------------------- #


class RuleCondition(BaseModel):
    """A named predicate plus its parameters.

    The predicate *vocabulary* is implemented in ``risk.engine`` (a fixed,
    auditable set). The predicate *parameters* (formats, foundry lists, CDN sets,
    thresholds) are pure data and live in ``rules.yaml`` — that is what makes the
    engine editable without touching code.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, description="Predicate name registered in risk.engine.")
    params: dict[str, Any] = Field(default_factory=dict)


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = ""
    weight: float = Field(ge=0, description="Points contributed when the rule fires.")
    confidence: float = Field(ge=0, le=1, description="Scales the weight (0..1).")
    when: RuleCondition


class BandThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medium: float = Field(ge=0, le=100)
    high: float = Field(ge=0, le=100)

    @field_validator("high")
    @classmethod
    def _high_above_medium(cls, value: float, info: Any) -> float:
        medium = info.data.get("medium")
        if medium is not None and value < medium:
            raise ValueError("band 'high' threshold must be >= 'medium' threshold")
        return value


class Scoring(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_raw: float = Field(gt=0, description="Raw weighted sum that maps to a score of 100.")
    bands: BandThresholds


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scoring: Scoring
    rules: list[Rule] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, rules: list[Rule]) -> list[Rule]:
        seen: set[str] = set()
        for rule in rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id: {rule.id!r}")
            seen.add(rule.id)
        return rules


# --------------------------------------------------------------------------- #
# License registry
# --------------------------------------------------------------------------- #


class RegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    foundry: str = Field(min_length=1)
    family: str = Field(min_length=1)
    license_type: str = Field(min_length=1)
    allowed_domains: list[str] = Field(default_factory=list)
    max_domains: int | None = Field(default=None, ge=1)
    proof_path: Path | None = None
    invoice_path: Path | None = None
    valid_until: date | None = None
    notes: str | None = None


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[RegistryEntry] = Field(default_factory=list)
