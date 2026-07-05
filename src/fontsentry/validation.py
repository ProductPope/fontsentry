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

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

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
    return (value or "").strip().lower()


def _find(fonts: list[DomainFont], label: FontLabel) -> DomainFont | None:
    for f in fonts:
        if _norm(f.family) != _norm(label.family):
            continue
        if label.owner is not None and _norm(f.owner) != _norm(label.owner):
            continue
        return f
    return None


def compare(report: RunReport, labels: Labels) -> ValidationResult:
    """Compare a run's per-domain verdicts against the human labels."""

    by_domain = {_norm(d.domain): d for d in report.domains}
    result = ValidationResult()

    for domain_label in labels.entries:
        domain_report = by_domain.get(_norm(domain_label.domain))
        fonts = domain_report.fonts if domain_report else []
        for font_label in domain_label.fonts:
            result.total += 1
            found = _find(fonts, font_label)
            if found is None:
                result.missing.append(
                    Mismatch(
                        domain=domain_label.domain,
                        family=font_label.family,
                        expected=font_label.expected,
                        actual=None,
                        note=font_label.note,
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
                        note=font_label.note,
                    )
                )

    return result


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
    return "\n".join(lines) + "\n"
