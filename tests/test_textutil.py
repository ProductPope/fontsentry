"""Charset-aware decoding of fetched bytes."""

from __future__ import annotations

from fontsentry.textutil import decode_text


def test_honors_content_type_charset() -> None:
    body = "Ténör".encode("latin-1")
    assert decode_text(body, "text/html; charset=latin-1") == "Ténör"


def test_defaults_to_utf8_when_no_charset() -> None:
    assert decode_text("café".encode(), "text/html") == "café"


def test_unknown_codec_falls_back_to_utf8() -> None:
    assert decode_text(b"hi", "text/css; charset=not-a-real-codec") == "hi"


def test_quoted_charset_value() -> None:
    body = "Ünïcode".encode("latin-1")
    assert decode_text(body, 'text/html; charset="latin-1"') == "Ünïcode"
