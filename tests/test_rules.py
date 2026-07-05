"""Unit tests for the classification helpers (edge cases, guards, boundaries)."""

from __future__ import annotations

from typing import Any

from fontsentry.models import (
    AggregatedFont,
    EmbeddingMethod,
    FamilySpec,
    FontFormat,
    FontMetadata,
)
from fontsentry.risk import rules as clf


def _agg(**kw: Any) -> AggregatedFont:
    return AggregatedFont(family=kw.pop("family", "Demo Sans"), **kw)


def _meta(**kw: Any) -> FontMetadata:
    return FontMetadata(**kw)


def test_family_is_paid_tier_empty_contains_all_never_matches() -> None:
    agg = _agg(family="Font Awesome 6 Pro")
    assert clf.family_is_paid_tier(agg, [FamilySpec(contains_all=[])]) is False


def test_family_is_paid_tier_excludes_suppresses() -> None:
    agg = _agg(family="Font Awesome 6 Pro Duotone")
    spec = FamilySpec(contains_all=["font awesome", "pro"], excludes=["duotone"])
    assert clf.family_is_paid_tier(agg, [spec]) is False


def test_family_is_paid_tier_positive() -> None:
    agg = _agg(family="Font Awesome 6 Pro")
    spec = FamilySpec(contains_all=["font awesome", "pro"])
    assert clf.family_is_paid_tier(agg, [spec]) is True


def test_subset_signal_strict_below_threshold_and_web_gate() -> None:
    web = {"formats": [FontFormat.WOFF2]}
    assert clf.subset_signal(_agg(metadata=_meta(num_glyphs=255), **web), 256) is True
    assert clf.subset_signal(_agg(metadata=_meta(num_glyphs=256), **web), 256) is False
    # No web format -> never a subset signal.
    ttf = _agg(metadata=_meta(num_glyphs=10), formats=[FontFormat.TTF])
    assert clf.subset_signal(ttf, 256) is False
    # No metadata / no glyph count -> False.
    assert clf.subset_signal(_agg(metadata=None, formats=[FontFormat.WOFF2]), 256) is False


def test_paid_cdn_delivery_skips_bad_name_matches_valid() -> None:
    agg = _agg(embeddings=[EmbeddingMethod.ADOBE_FONTS])
    assert clf.paid_cdn_delivery(agg, ["adobe_fonts", "not_a_real_method"]) is True


def test_missing_license_string() -> None:
    empty = _agg(metadata=_meta(copyright="", license_description=""))
    assert clf.missing_license_string(empty) is True
    full = _meta(copyright="c 2026", license_description="lic")
    assert clf.missing_license_string(_agg(metadata=full)) is False
    # No metadata -> no evidence either way.
    assert clf.missing_license_string(_agg(metadata=None)) is False


def test_self_host_prohibited_requires_self_hosted_and_folds_case() -> None:
    # Not self-hosted -> False even if owner matches.
    not_hosted = _agg(owner="Meridian Letterworks", embeddings=[EmbeddingMethod.GOOGLE_FONTS])
    assert clf.self_host_prohibited(not_hosted, ["Meridian Letterworks"], []) is False
    # Self-hosted + owner match (case-insensitive) -> True.
    hosted = _agg(owner="meridian letterworks", embeddings=[EmbeddingMethod.SELF_HOSTED])
    assert clf.self_host_prohibited(hosted, ["Meridian Letterworks"], []) is True


def test_desktop_format_on_web_excludes_system_only() -> None:
    agg = _agg(formats=[FontFormat.TTF], embeddings=[EmbeddingMethod.SYSTEM])
    assert clf.desktop_format_on_web(agg, ["ttf"]) is False
    served = _agg(formats=[FontFormat.TTF], embeddings=[EmbeddingMethod.SELF_HOSTED])
    assert clf.desktop_format_on_web(served, ["ttf"]) is True


def test_open_signals() -> None:
    ofl = _agg(metadata=_meta(license_description="SIL Open Font License (OFL)"))
    assert clf.looks_open_licensed(ofl, ["OFL"]) is True
    assert clf.owner_is_free(_agg(owner="Public Glyphs Foundation"), ["Public Glyphs Foundation"])
    fa = _agg(family="Font Awesome 5 Free")
    assert clf.family_is_open(fa, [FamilySpec(contains_all=["font awesome"], excludes=["pro"])])
