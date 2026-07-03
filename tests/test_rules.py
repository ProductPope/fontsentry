"""Unit tests for individual rule predicates (edge cases, guards, boundaries)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fontsentry.models import AggregatedFont, EmbeddingMethod, FontFormat, FontMetadata
from fontsentry.risk.rules import (
    PredicateContext,
    commercial_unregistered,
    family_name_matches,
    format_on_web,
    missing_name_field,
    paid_cdn_unregistered,
    self_host_prohibited,
    subset_signal,
)

NOW = date(2026, 6, 30)


def _ctx(params: dict[str, Any], **agg_kw: Any) -> PredicateContext:
    agg = AggregatedFont(family=agg_kw.pop("family", "Demo Sans"), **agg_kw)
    return PredicateContext(agg=agg, entry=None, now=NOW, params=params)


def _meta(**kw: Any) -> FontMetadata:
    return FontMetadata(**kw)


def test_family_name_matches_empty_contains_all_never_matches() -> None:
    assert family_name_matches(_ctx({"contains_all": []}, family="Font Awesome 6 Pro")) is False


def test_family_name_matches_excludes_suppresses() -> None:
    ctx = _ctx(
        {"contains_all": ["font awesome", "pro"], "excludes": ["duotone"]},
        family="Font Awesome 6 Pro Duotone",
    )
    assert family_name_matches(ctx) is False


def test_family_name_matches_positive() -> None:
    ctx = _ctx({"contains_all": ["font awesome", "pro"]}, family="Font Awesome 6 Pro")
    assert family_name_matches(ctx) is True


def test_subset_signal_strict_below_threshold_and_web_gate() -> None:
    web = {"formats": [FontFormat.WOFF2]}
    assert subset_signal(_ctx({"max_glyphs": 256}, metadata=_meta(num_glyphs=255), **web)) is True
    assert subset_signal(_ctx({"max_glyphs": 256}, metadata=_meta(num_glyphs=256), **web)) is False
    # No web format -> never a subset signal.
    assert (
        subset_signal(
            _ctx({"max_glyphs": 256}, metadata=_meta(num_glyphs=10), formats=[FontFormat.TTF])
        )
        is False
    )
    # No metadata / no glyph count -> False.
    assert subset_signal(_ctx({}, metadata=None, formats=[FontFormat.WOFF2])) is False


def test_paid_cdn_unregistered_skips_bad_name_matches_valid() -> None:
    ctx = _ctx(
        {"cdns": ["adobe_fonts", "not_a_real_method"]},
        embeddings=[EmbeddingMethod.ADOBE_FONTS],
    )
    assert paid_cdn_unregistered(ctx) is True


def test_missing_name_field_empty_fires_unknown_field_ignored() -> None:
    # Empty copyright fires; but an unknown/misspelled field name must NOT fire.
    assert missing_name_field(_ctx({"fields": ["copyright"]}, metadata=_meta(copyright=""))) is True
    full = _meta(copyright="c 2026", license_description="lic")
    assert missing_name_field(_ctx({"fields": ["bogus_field"]}, metadata=full)) is False


def test_missing_name_field_no_metadata_is_false() -> None:
    assert missing_name_field(_ctx({"fields": ["copyright"]}, metadata=None)) is False


def test_commercial_unregistered_requires_metadata_evidence() -> None:
    # No metadata -> we don't assert "commercial".
    assert commercial_unregistered(_ctx({}, metadata=None)) is False


def test_self_host_prohibited_requires_self_hosted_and_folds_case() -> None:
    prohibited = {"owners": ["Meridian Letterworks"], "families": []}
    # Not self-hosted -> False even if owner matches.
    assert (
        self_host_prohibited(
            _ctx(
                prohibited, owner="Meridian Letterworks", embeddings=[EmbeddingMethod.GOOGLE_FONTS]
            )
        )
        is False
    )
    # Self-hosted + owner match (case-insensitive) -> True.
    assert (
        self_host_prohibited(
            _ctx(prohibited, owner="meridian letterworks", embeddings=[EmbeddingMethod.SELF_HOSTED])
        )
        is True
    )


def test_format_on_web_excludes_system_only() -> None:
    ctx = _ctx({"formats": ["ttf"]}, formats=[FontFormat.TTF], embeddings=[EmbeddingMethod.SYSTEM])
    assert format_on_web(ctx) is False
