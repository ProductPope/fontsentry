"""Classify how a font is embedded, from the font (or stylesheet) URL.

Known-provider host patterns are detection facts, not risk policy, so they live in
code here. Risk weighting of these providers is configured separately in rules.yaml.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from fontsentry.models import EmbeddingMethod

# provider host -> provider, matched exact-or-dot-bounded-subdomain (see
# host_matches). Checked in order; first match wins.
_PROVIDER_PATTERNS: tuple[tuple[str, EmbeddingMethod], ...] = (
    ("fonts.gstatic.com", EmbeddingMethod.GOOGLE_FONTS),
    ("fonts.googleapis.com", EmbeddingMethod.GOOGLE_FONTS),
    ("use.typekit.net", EmbeddingMethod.ADOBE_FONTS),
    ("use.typekit.com", EmbeddingMethod.ADOBE_FONTS),
    ("p.typekit.net", EmbeddingMethod.ADOBE_FONTS),
    ("use.edgefonts.net", EmbeddingMethod.ADOBE_FONTS),
    ("typekit.com", EmbeddingMethod.ADOBE_FONTS),
    ("fast.fonts.net", EmbeddingMethod.MONOTYPE),
    ("fonts.net", EmbeddingMethod.MONOTYPE),
    ("fonts.com", EmbeddingMethod.MONOTYPE),
    ("hello.myfonts.net", EmbeddingMethod.MONOTYPE),
    ("myfonts.net", EmbeddingMethod.MONOTYPE),
    ("monotype.com", EmbeddingMethod.MONOTYPE),
)

# Generic CDN host markers: not the site's own host, but not a font provider either.
_GENERIC_CDN_MARKERS: tuple[str, ...] = (
    "cloudfront.net",
    "akamaihd.net",
    "akamai.net",
    "fastly.net",
    "jsdelivr.net",
    "unpkg.com",
    "bootstrapcdn.com",
    "cdnjs.cloudflare.com",
    "cdn.",
    "assets.",
    "static.",
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def host_matches(host: str, marker: str) -> bool:
    """Exact host or a dot-bounded subdomain of ``marker``. A bare substring test
    would let ``use.typekit.net.evil.example`` read as a known provider — and a
    provider mislabel changes both the privacy verdict and the license evidence."""
    return host == marker or host.endswith("." + marker)


def _same_site(host: str, page_host: str) -> bool:
    # Exact host or a dot-bounded subdomain only. A bare suffix test would wrongly
    # treat notexample.com / evilexample.com as same-site with example.com, which
    # would clear the third-party (privacy) signal for an attacker-controlled host.
    host = host.lower()
    page_host = page_host.lower().removeprefix("www.")
    return host == page_host or host.endswith("." + page_host)


def classify_embedding(
    font_url: str | None,
    page_host: str | None = None,
    own_hosts: Iterable[str] = (),
) -> EmbeddingMethod:
    """Classify the embedding method for a font referenced by ``font_url``.

    A relative URL (no host) or a URL on the page's own host is ``SELF_HOSTED``.
    ``own_hosts`` lets the operator declare their own asset domains (e.g. a CDN on
    a separate domain) as first-party too. Known providers map to their method;
    anything else on a CDN-like host is ``OTHER_CDN``; remaining off-host URLs
    default to ``OTHER_CDN`` as well.
    """

    if not font_url:
        return EmbeddingMethod.SELF_HOSTED

    host = _host(font_url)
    if not host:
        # Relative or data: URL -> served from the same origin.
        return EmbeddingMethod.SELF_HOSTED

    for marker, method in _PROVIDER_PATTERNS:
        if host_matches(host, marker):
            return method

    if page_host and _same_site(host, page_host):
        return EmbeddingMethod.SELF_HOSTED

    # Operator-declared own hosts (assets on a separate domain they control).
    if any(_same_site(host, own) for own in own_hosts if own):
        return EmbeddingMethod.SELF_HOSTED

    if any(marker in host for marker in _GENERIC_CDN_MARKERS):
        return EmbeddingMethod.OTHER_CDN

    # Off-host, unknown provider: treat as third-party CDN.
    return EmbeddingMethod.OTHER_CDN
