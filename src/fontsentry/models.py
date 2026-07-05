"""Pydantic domain models shared across the package.

Config-side models (settings, targets, rules, registry) live here. Runtime models
produced during a scan (detected fonts, findings) are added by the detect/risk
phases. Enums are shared by everything, so they live here too.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

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


class LicenseVerdict(StrEnum):
    """Deterministic license classification (ADR 0003). Nuance lives in the reason.

    OK          — no action needed: covered by a registry license, provably open,
                  or a system/fallback font (no license question).
    NEEDS_CHECK  — the honest default: no license on record and not provably open;
                  a human should look. Carries evidence notes explaining why.
    VIOLATION    — a definite lapse: a declared license expired or out of scope /
                  over max_domains, a paid tier served without cover, or a
                  self-host-prohibited font self-hosted without cover.
    """

    OK = "ok"
    NEEDS_CHECK = "needs_check"
    VIOLATION = "violation"


class PrivacyClass(StrEnum):
    """How a font's delivery affects visitor privacy — the axis is independent of
    the license risk band. Third-party delivery (e.g. the Google Fonts API) sends
    each visitor's IP to that third party, a GDPR/RODO concern even when the font
    itself is freely licensed."""

    SELF_HOSTED = "self_hosted"  # served from the site's own hosts — no leakage
    THIRD_PARTY_API = "third_party_api"  # served from a third party (Google/Adobe/CDN)
    MIXED = "mixed"  # both self-hosted and third-party across pages
    NOT_APPLICABLE = "not_applicable"  # system/fallback font — nothing is downloaded


class FindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


# --------------------------------------------------------------------------- #
# Detection runtime models
# --------------------------------------------------------------------------- #


# Report models are machine-written and read back across tool versions, so they
# tolerate unknown fields (forward/back-compat): an old report with a since-removed
# field still loads. Config models (human-edited YAML) stay extra="forbid" to catch
# typos. See docs/rules.md / CHANGELOG.
_REPORT_MODEL_CONFIG = ConfigDict(extra="ignore")


class FontMetadata(BaseModel):
    """Fields read from a font file's `name` table (any may be missing/stripped)."""

    model_config = _REPORT_MODEL_CONFIG

    family_name: str | None = None
    owner: str | None = None  # name ID 8 (manufacturer)
    designer: str | None = None  # name ID 9
    copyright: str | None = None  # name ID 0
    license_description: str | None = None  # name ID 13
    license_url: str | None = None  # name ID 14
    unique_id: str | None = None  # name ID 3
    num_glyphs: int | None = None
    fs_type: int | None = None  # OS/2 fsType embedding-permission bits


class DetectedFont(BaseModel):
    """A single font occurrence found on one page."""

    model_config = ConfigDict(extra="forbid")

    family: str
    embedding: EmbeddingMethod
    font_format: FontFormat = FontFormat.UNKNOWN
    source_page: str
    font_url: str | None = None
    metadata: FontMetadata | None = None
    # False when the family is declared via @font-face but not referenced by any
    # font-family usage on the page (served but not applied to any text).
    applied: bool = True


class AggregatedFont(BaseModel):
    """One font identity (family + owner) merged across every domain it appears on."""

    model_config = ConfigDict(extra="forbid")

    family: str
    family_group: str = ""  # base family with weight/style variants folded away
    owner: str | None = None
    domains: list[str] = Field(default_factory=list)
    formats: list[FontFormat] = Field(default_factory=list)
    embeddings: list[EmbeddingMethod] = Field(default_factory=list)
    metadata: FontMetadata | None = None
    occurrences: int = 0
    example_urls: list[str] = Field(default_factory=list)  # sample pages the font was seen on
    page_count: int = 0  # distinct pages the font was seen on
    applied: bool = True  # referenced by a font-family usage somewhere (not just @font-face)
    privacy: PrivacyClass = PrivacyClass.NOT_APPLICABLE  # delivery-based privacy axis

    @property
    def domain_count(self) -> int:
        return len(self.domains)


class Finding(BaseModel):
    """A classified font identity: the unit of a report (ADR 0003, deterministic)."""

    model_config = _REPORT_MODEL_CONFIG

    family: str
    family_group: str = ""  # base family with weight/style variants folded away
    owner: str | None = None
    domains: list[str] = Field(default_factory=list)
    formats: list[FontFormat] = Field(default_factory=list)
    embeddings: list[EmbeddingMethod] = Field(default_factory=list)
    metadata: FontMetadata | None = None
    # Deterministic verdicts, each with an explicit reason.
    license_verdict: LicenseVerdict = LicenseVerdict.NEEDS_CHECK
    license_reason: str = ""
    evidence_notes: list[str] = Field(default_factory=list)  # inform NEEDS_CHECK; never decide
    privacy: PrivacyClass = PrivacyClass.NOT_APPLICABLE  # delivery-based privacy axis
    registry_match: bool = False
    example_urls: list[str] = Field(default_factory=list)  # sample pages the font was seen on
    page_count: int = 0  # distinct pages the font was seen on
    applied: bool = True  # False = served via @font-face but not applied to any text

    @property
    def domain_count(self) -> int:
        return len(self.domains)

    @property
    def needs_action(self) -> bool:
        """True when a human should look: a license concern or a privacy leak."""
        return self.license_verdict is not LicenseVerdict.OK or self.privacy in (
            PrivacyClass.THIRD_PARTY_API,
            PrivacyClass.MIXED,
        )


class RunSummary(BaseModel):
    """Headline counts for one scan run."""

    model_config = _REPORT_MODEL_CONFIG

    total_findings: int = 0
    needs_action: int = 0  # license verdict != OK, or a third-party/mixed privacy leak
    by_verdict: dict[LicenseVerdict, int] = Field(default_factory=dict)
    by_privacy: dict[PrivacyClass, int] = Field(default_factory=dict)


class HostAsset(BaseModel):
    """The font-file URL(s) a font was served from on one host."""

    model_config = _REPORT_MODEL_CONFIG

    host: str
    urls: list[str] = Field(default_factory=list)


class DomainFont(BaseModel):
    """A font used on one domain, with how it was embedded and the hosts it was seen on."""

    model_config = _REPORT_MODEL_CONFIG

    family: str
    owner: str | None = None
    license_verdict: LicenseVerdict = LicenseVerdict.NEEDS_CHECK
    license_reason: str = ""
    privacy: PrivacyClass = PrivacyClass.NOT_APPLICABLE
    embeddings: list[EmbeddingMethod] = Field(default_factory=list)
    formats: list[FontFormat] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)
    # Per-host font-file URLs (asset paths). Empty for pre-v4 reports and for
    # fonts with no directly fetched file (e.g. some CDN/API embeddings).
    assets: list[HostAsset] = Field(default_factory=list)


class DomainReport(BaseModel):
    """The domain-centric view of a scan: one target domain and what was found on it."""

    model_config = _REPORT_MODEL_CONFIG

    domain: str
    is_live: bool = False
    pages_scanned: int = 0
    live_hosts: list[str] = Field(default_factory=list)
    subdomains: list[str] = Field(default_factory=list)
    fonts: list[DomainFont] = Field(default_factory=list)


class RunReport(BaseModel):
    """A complete scan run: the JSON source of truth that every output derives from."""

    model_config = _REPORT_MODEL_CONFIG

    schema_version: int = 9
    generated_at: datetime
    duration_seconds: float = 0.0  # wall-clock scan time; powers ETA estimates
    summary: RunSummary
    findings: list[Finding] = Field(default_factory=list)
    domains: list[DomainReport] = Field(default_factory=list)


class FindingDelta(BaseModel):
    """A finding present in both runs whose verdict or domain spread changed."""

    model_config = ConfigDict(extra="forbid")

    family: str
    owner: str | None = None
    old_verdict: LicenseVerdict
    new_verdict: LicenseVerdict
    old_domains: list[str] = Field(default_factory=list)
    new_domains: list[str] = Field(default_factory=list)


class DiffResult(BaseModel):
    """The difference between two runs, over findings that need action."""

    model_config = ConfigDict(extra="forbid")

    new_findings: list[Finding] = Field(default_factory=list)
    resolved_findings: list[Finding] = Field(default_factory=list)
    changed: list[FindingDelta] = Field(default_factory=list)
    unchanged_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new_findings or self.resolved_findings or self.changed)


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
        default="FontSentry/0.1 (+https://github.com/ProductPope/fontsentry)",
        min_length=1,
    )
    respect_robots: bool = True
    discover_subdomains: bool = Field(
        default=True, description="Passive subdomain discovery (sitemap, links, seeds) only."
    )
    max_response_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        description="Hard cap on any fetched body (also bounds decompressed size).",
    )
    max_redirects: int = Field(default=5, ge=0, description="Max redirect hops per request.")
    block_private_hosts: bool = Field(
        default=True,
        description=(
            "Refuse to fetch hosts that resolve to loopback/private/link-local IPs "
            "(SSRF guard). Turn OFF only to audit internal/staging sites on a private network."
        ),
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
# Classification config (ADR 0003): pure data for the deterministic decision
# table. No weights, no thresholds — mechanics live in fontsentry.risk.
# --------------------------------------------------------------------------- #


class FamilySpec(BaseModel):
    """Match a font by family name: contains every substring in `contains_all`
    (case-insensitive) and none in `excludes`. Empty `contains_all` never matches."""

    model_config = ConfigDict(extra="forbid")

    contains_all: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)


class SelfHostProhibited(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owners: list[str] = Field(default_factory=list)
    families: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    """Classification data for the verdict engine (editable without touching code)."""

    model_config = ConfigDict(extra="forbid")

    # Provably-OPEN signals (any -> license OK without a registry entry).
    open_license_patterns: list[str] = Field(default_factory=list)
    free_owners: list[str] = Field(default_factory=list)
    open_families: list[FamilySpec] = Field(default_factory=list)

    # Definite-VIOLATION signals (when no valid registry cover applies).
    paid_tier_families: list[FamilySpec] = Field(default_factory=list)
    self_host_prohibited: SelfHostProhibited = Field(default_factory=SelfHostProhibited)

    # Evidence-note signals (context for NEEDS_CHECK — they never decide a verdict).
    paid_cdns: list[str] = Field(default_factory=list)  # embedding methods, e.g. adobe_fonts
    desktop_formats: list[str] = Field(default_factory=list)  # e.g. ttf, otf
    subset_max_glyphs: int = Field(default=256, ge=0)


# --------------------------------------------------------------------------- #
# License registry
# --------------------------------------------------------------------------- #


class RegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1)
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
