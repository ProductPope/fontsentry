"""Verdict validation: matching tool verdicts against human labels (offline)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fontsentry.models import (
    DomainFont,
    DomainReport,
    LicenseVerdict,
    RunReport,
    RunSummary,
)
from fontsentry.validation import (
    DomainLabel,
    FontLabel,
    Labels,
    compare,
    coverage_failure,
    load_labels,
    render_summary,
)

OK = LicenseVerdict.OK
NEEDS_CHECK = LicenseVerdict.NEEDS_CHECK
VIOLATION = LicenseVerdict.VIOLATION


def _report() -> RunReport:
    return RunReport(
        generated_at=datetime(2026, 7, 5, 12, 0, 0),
        summary=RunSummary(),
        domains=[
            DomainReport(
                domain="a.com",
                fonts=[
                    DomainFont(family="Alpha", owner="Acme", license_verdict=OK),
                    DomainFont(family="Beta", license_verdict=NEEDS_CHECK),
                    DomainFont(family="Gamma", license_verdict=OK),
                ],
            )
        ],
    )


def _labels() -> Labels:
    return Labels(
        entries=[
            DomainLabel(
                domain="a.com",
                fonts=[
                    FontLabel(family="Alpha", owner="Acme", expected=OK),  # match
                    FontLabel(family="Beta", expected=VIOLATION),  # safe mismatch
                    FontLabel(family="Gamma", expected=VIOLATION),  # FALSE NEGATIVE (actual OK)
                    FontLabel(family="Missing", expected=NEEDS_CHECK),  # not detected
                ],
            )
        ]
    )


def test_compare_categorises_every_label() -> None:
    result = compare(_report(), _labels())
    assert result.total == 4
    assert result.matched == 1
    assert {m.family for m in result.mismatched} == {"Beta", "Gamma"}
    assert [m.family for m in result.missing] == ["Missing"]
    assert [m.family for m in result.false_negatives] == ["Gamma"]
    assert result.agreement_rate == 1 / 3  # matched / (matched + mismatched)


def test_owner_mismatch_is_not_found() -> None:
    report = _report()
    fonts = [FontLabel(family="Alpha", owner="Other", expected=OK)]
    labels = Labels(entries=[DomainLabel(domain="a.com", fonts=fonts)])
    result = compare(report, labels)
    assert [m.family for m in result.missing] == ["Alpha"]  # owner didn't match -> not detected


def test_unlabelled_domain_yields_missing() -> None:
    labels = Labels(
        entries=[DomainLabel(domain="unscanned.com", fonts=[FontLabel(family="X", expected=OK)])]
    )
    result = compare(_report(), labels)
    assert result.total == 1
    assert len(result.missing) == 1


def test_render_summary_flags_false_negatives() -> None:
    text = render_summary(compare(_report(), _labels()))
    assert "False negatives" in text
    assert "Gamma" in text
    assert "agreement" in text


def test_zero_detection_fails_coverage_gate() -> None:
    # Regression: a broken scan (network down, hosts blocked) detects nothing,
    # so it has zero false negatives *vacuously* — it must not read as "validated".
    empty_report = RunReport(
        generated_at=datetime(2026, 7, 5, 12, 0, 0), summary=RunSummary(), domains=[]
    )
    result = compare(empty_report, _labels())
    assert result.false_negatives == []  # the vacuous pass the gate exists to catch
    assert coverage_failure(result, max_missing=0.5) is not None


def test_empty_labels_fail_coverage_gate() -> None:
    result = compare(_report(), Labels())
    assert coverage_failure(result, max_missing=0.5) is not None


def test_missing_ratio_over_limit_fails_coverage_gate() -> None:
    result = compare(_report(), _labels())  # 1 of 4 labels missing (25%)
    assert coverage_failure(result, max_missing=0.5) is None
    assert coverage_failure(result, max_missing=0.2) is not None
    assert "--max-missing" in (coverage_failure(result, max_missing=0.2) or "")


def test_load_labels_roundtrip(tmp_path: Path, repo_root: Path) -> None:
    example = (repo_root / "validation" / "labels.example.yaml").read_text(encoding="utf-8")
    path = tmp_path / "labels.yaml"
    path.write_text(example, encoding="utf-8")
    labels = load_labels(path)
    assert labels.entries[0].domain == "example.com"
    assert labels.entries[0].fonts[0].expected in set(LicenseVerdict)
