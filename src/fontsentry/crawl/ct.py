"""Opt-in public-subdomain discovery via Certificate Transparency (crt.sh).

This is NOT passive-within-the-target and NOT local: it queries an external
public service (crt.sh) that indexes TLS certificates, so the target domain
leaves the machine. It is therefore off by default and only runs when the user
explicitly enables it for a scan. It never brute-forces DNS.
"""

from __future__ import annotations

import httpx


async def ct_subdomains(
    client: httpx.AsyncClient, domain: str, *, timeout: float = 20.0
) -> list[str]:
    """Return public subdomains of ``domain`` seen in Certificate Transparency logs.

    Best-effort: any network/parse error yields an empty list (the scan then
    proceeds with passive discovery only). Wildcards and the apex are excluded.
    """

    try:
        resp = await client.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    if not isinstance(rows, list):
        return []

    suffix = "." + domain.lower()
    found: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name in str(row.get("name_value", "")).splitlines():
            host = name.strip().lower().removeprefix("*.").rstrip(".")
            if host and host != domain.lower() and host.endswith(suffix):
                found.add(host)
    return sorted(found)
