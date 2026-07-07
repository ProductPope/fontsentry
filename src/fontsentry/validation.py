"""Verdict-rule validation against a human-labelled ground truth (roadmap Phase 8).

This confirms the *rules themselves* match real-world judgement — not that the code
is deterministic (unit tests already pin that). The comparison here is pure and
offline-testable; driving a real scan to produce the report is the CLI's job.

A label file (`validation/labels.yaml`) records, per domain, the human verdict for
each font. The harness matches the tool's per-domain verdicts against those labels
and reports agreement, mismatches, and — separately — false negatives (the unsafe
direction: the tool said OK where a human said otherwise).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from fontsentry.families import group_key
from fontsentry.models import DomainFont, LicenseVerdict, RunReport


class FontLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str = Field(min_length=1)
    owner: str | None = None  # optional; when set, both family and owner must match
    expected: LicenseVerdict
    note: str = ""


class DomainLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    fonts: list[FontLabel] = Field(default_factory=list)


class Labels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[DomainLabel] = Field(default_factory=list)


class Mismatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    family: str
    expected: LicenseVerdict
    actual: LicenseVerdict | None  # None = the labelled font was not detected
    note: str = ""


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    matched: int = 0
    mismatched: list[Mismatch] = Field(default_factory=list)
    missing: list[Mismatch] = Field(default_factory=list)
    # Labelled domains the scan produced no report for at all — usually a typo
    # in the label file or a fully blocked host; called out so a whole domain
    # can't silently drain into `missing`.
    unmatched_domains: list[str] = Field(default_factory=list)

    @property
    def agreement_rate(self) -> float:
        """Share of labelled fonts whose verdict the tool got right (detected only)."""
        judged = self.matched + len(self.mismatched)
        return self.matched / judged if judged else 0.0

    @property
    def false_negatives(self) -> list[Mismatch]:
        """The unsafe direction: tool said OK where the human did not."""
        return [
            m
            for m in self.mismatched
            if m.actual is LicenseVerdict.OK and m.expected is not LicenseVerdict.OK
        ]


def load_labels(path: Path) -> Labels:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Labels.model_validate(data)


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).lower()


# PDF-style subset tag prefix (ABCDEF+FontName) — strip it before matching.
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def _family_key(value: str) -> str:
    """Match key for family names: subset prefix stripped, weight/style variants
    folded (the pipeline's own grouping), punctuation/case-insensitive — so a
    label "Open Sans" matches a detected "OpenSans-Regular"."""

    return group_key(_SUBSET_PREFIX.sub("", value.strip()))


def _domain_key(value: str) -> str:
    v = value.strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix) :]
    v = v.split("/", 1)[0]
    return v.removeprefix("www.")


def _find(fonts: list[DomainFont], label: FontLabel) -> tuple[DomainFont | None, str]:
    """Return (match, owner_note). A label that names a family the tool detected
    is a *judged* comparison even when the owner differs or the file's owner is
    stripped — silently reclassifying it as "not detected" would remove it from
    the agreement denominator and from the false-negative gate."""

    key = _family_key(label.family)
    same_family = [f for f in fonts if _family_key(f.family) == key]
    if not same_family:
        return None, ""
    if label.owner is None:
        return same_family[0], ""
    for f in same_family:
        if _norm(f.owner) == _norm(label.owner):
            return f, ""
    file_owner = same_family[0].owner or "none in the font file"
    return same_family[0], f"owner differs (label: {label.owner!r}, file: {file_owner!r})"


def compare(report: RunReport, labels: Labels) -> ValidationResult:
    """Compare a run's per-domain verdicts against the human labels."""

    by_domain = {_domain_key(d.domain): d for d in report.domains}
    result = ValidationResult()

    for domain_label in labels.entries:
        domain_report = by_domain.get(_domain_key(domain_label.domain))
        if domain_report is None and domain_label.fonts:
            result.unmatched_domains.append(domain_label.domain)
        fonts = domain_report.fonts if domain_report else []
        for font_label in domain_label.fonts:
            result.total += 1
            found, owner_note = _find(fonts, font_label)
            note = "; ".join(n for n in (font_label.note, owner_note) if n)
            if found is None:
                result.missing.append(
                    Mismatch(
                        domain=domain_label.domain,
                        family=font_label.family,
                        expected=font_label.expected,
                        actual=None,
                        note=note,
                    )
                )
            elif found.license_verdict is font_label.expected:
                result.matched += 1
            else:
                result.mismatched.append(
                    Mismatch(
                        domain=domain_label.domain,
                        family=font_label.family,
                        expected=font_label.expected,
                        actual=found.license_verdict,
                        note=note,
                    )
                )

    return result


def coverage_failure(result: ValidationResult, max_missing: float) -> str | None:
    """Why this run cannot support a verdict-rule conclusion — or None if it can.

    A font can only be a false negative if it was detected, so a broken scan
    (network down, every host blocked) detects nothing, produces zero false
    negatives vacuously, and would pass the unsafe-direction gate. Detection
    coverage is therefore a precondition of the verdict comparison, not a nicety.
    """

    if result.total == 0:
        return "no labelled fonts were loaded — nothing to validate"
    judged = result.matched + len(result.mismatched)
    if judged == 0:
        return "no labelled font was detected at all — the scan looks broken, not validated"
    missing_ratio = len(result.missing) / result.total
    if missing_ratio > max_missing:
        return (
            f"{len(result.missing)} of {result.total} labelled fonts were not detected "
            f"({missing_ratio:.0%} > the --max-missing limit of {max_missing:.0%})"
        )
    return None


def render_summary(result: ValidationResult) -> str:
    """A short markdown report of the validation run (for the terminal or docs)."""

    lines = [
        "# Verdict validation",
        "",
        f"- Labelled fonts: **{result.total}**",
        f"- Detected & judged: **{result.matched + len(result.mismatched)}** "
        f"(agreement **{result.agreement_rate:.0%}**)",
        f"- Matched: **{result.matched}**",
        f"- Mismatched: **{len(result.mismatched)}** "
        f"(of which false-negatives / unsafe: **{len(result.false_negatives)}**)",
        f"- Not detected: **{len(result.missing)}**",
    ]

    def _rows(title: str, items: list[Mismatch]) -> None:
        if not items:
            return
        lines.append("")
        lines.append(f"## {title}")
        for m in items:
            actual = m.actual.value if m.actual else "—"
            note = f" — {m.note}" if m.note else ""
            lines.append(
                f"- `{m.domain}` **{m.family}**: expected {m.expected.value}, got {actual}{note}"
            )

    _rows("False negatives (tool said OK, human did not)", result.false_negatives)
    _rows("Other mismatches", [m for m in result.mismatched if m not in result.false_negatives])
    _rows("Not detected", result.missing)
    if result.unmatched_domains:
        lines.append("")
        lines.append("## Labelled domains with no scan result (typo? blocked host?)")
        lines.extend(f"- `{d}`" for d in result.unmatched_domains)
    return "\n".join(lines) + "\n"
