"""Embedding-method classification from font/stylesheet URLs."""

from __future__ import annotations

import pytest

from fontsentry.detect.embedding import classify_embedding
from fontsentry.models import EmbeddingMethod


@pytest.mark.parametrize(
    ("url", "page_host", "expected"),
    [
        ("https://fonts.gstatic.com/s/x/font.woff2", None, EmbeddingMethod.GOOGLE_FONTS),
        ("https://fonts.googleapis.com/css?family=X", None, EmbeddingMethod.GOOGLE_FONTS),
        ("https://use.typekit.net/abc.css", None, EmbeddingMethod.ADOBE_FONTS),
        ("https://p.typekit.net/x.woff", None, EmbeddingMethod.ADOBE_FONTS),
        ("https://fast.fonts.net/x.woff", None, EmbeddingMethod.MONOTYPE),
        ("https://hello.myfonts.net/x.woff", None, EmbeddingMethod.MONOTYPE),
        ("/fonts/local.woff2", None, EmbeddingMethod.SELF_HOSTED),
        ("https://example.com/fonts/local.woff2", "example.com", EmbeddingMethod.SELF_HOSTED),
        ("https://www.example.com/f.woff2", "example.com", EmbeddingMethod.SELF_HOSTED),
        ("https://cdn.example.com/f.woff2", "example.com", EmbeddingMethod.SELF_HOSTED),
        # Look-alike hosts must NOT be treated as same-site (no dot boundary).
        ("https://notexample.com/f.woff2", "example.com", EmbeddingMethod.OTHER_CDN),
        ("https://evilexample.com/f.woff2", "example.com", EmbeddingMethod.OTHER_CDN),
        ("https://cdn.example-cdn.net/f.woff2", "example.com", EmbeddingMethod.OTHER_CDN),
        ("https://d123.cloudfront.net/f.woff2", "example.com", EmbeddingMethod.OTHER_CDN),
        ("https://random-host.test/f.woff2", "example.com", EmbeddingMethod.OTHER_CDN),
    ],
)
def test_classify_embedding(url: str, page_host: str | None, expected: EmbeddingMethod) -> None:
    assert classify_embedding(url, page_host) is expected


def test_data_uri_is_self_hosted() -> None:
    assert classify_embedding("data:font/woff2;base64,AAAA") is EmbeddingMethod.SELF_HOSTED


def test_provider_match_wins_over_same_site() -> None:
    # A known provider host is classified as the provider even if page_host looks related.
    assert (
        classify_embedding("https://fonts.gstatic.com/f.woff2", "gstatic.com")
        is EmbeddingMethod.GOOGLE_FONTS
    )


def test_none_url_is_self_hosted() -> None:
    assert classify_embedding(None) is EmbeddingMethod.SELF_HOSTED


def test_own_hosts_are_first_party() -> None:
    # An operator-declared asset domain on a separate host is self-hosted.
    assert (
        classify_embedding(
            "https://assets.mybrand.net/f.woff2", "mybrand.com", own_hosts=["assets.mybrand.net"]
        )
        is EmbeddingMethod.SELF_HOSTED
    )
    # ...but without declaring it, a separate domain stays third-party.
    assert (
        classify_embedding("https://assets.mybrand.net/f.woff2", "mybrand.com")
        is EmbeddingMethod.OTHER_CDN
    )
