"""Certificate Transparency subdomain lookup — offline via httpx.MockTransport."""

from __future__ import annotations

import httpx

from fontsentry.crawl.ct import ct_subdomains


async def test_ct_subdomains_parses_and_filters() -> None:
    payload = [
        {"name_value": "blog.example.com\n*.example.com"},
        {"name_value": "shop.example.com"},
        {"name_value": "other.net"},  # different domain — excluded
        {"name_value": "example.com"},  # apex — excluded
        {"name_value": "BLOG.EXAMPLE.COM"},  # case-insensitive dedupe
    ]
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    )
    try:
        subs = await ct_subdomains(client, "example.com")
    finally:
        await client.aclose()
    assert subs == ["blog.example.com", "shop.example.com"]


async def test_ct_subdomains_returns_empty_on_error() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(500)))
    try:
        assert await ct_subdomains(client, "example.com") == []
    finally:
        await client.aclose()
