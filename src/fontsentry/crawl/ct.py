"""Opt-in public-subdomain discovery via Certificate Transparency (crt.sh).

This is NOT passive-within-the-target and NOT local: it queries an external
public service (crt.sh) that indexes TLS certificates, so the target domain
leaves the machine. It is therefore off by default and only runs when the user
explicitly enables it for a scan. It never brute-forces DNS.
"""

from __future__ import annotations

import asyncio

import httpx


async def ct_subdomains(
    client: httpx.AsyncClient,
    domain: str,
    *,
    timeout: float = 20.0,
    attempts: int = 3,
    backoff: float = 2.0,
) -> list[str]:
    """Return public subdomains of ``domain`` seen in Certificate Transparency logs.

    Best-effort: crt.sh is frequently overloaded (502s and non-JSON 200s), so
    transient failures are retried a few times with a short backoff before
    giving up. Any final failure yields an empty list (the scan then proceeds
    with passive discovery only). Wildcards and the apex are excluded.
    """

    suffix = "." + domain.lower()
    for attempt in range(attempts):
        try:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{domain}", "output": "json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError):
            # Transient (5xx, timeout, or a non-JSON interstitial) — retry.
            if attempt + 1 < attempts:
                await asyncio.sleep(backoff)
                continue
            return []

        if not isinstance(rows, list):
            return []  # valid JSON but unexpected shape — not worth retrying

        found: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            for name in str(row.get("name_value", "")).splitlines():
                host = name.strip().lower().removeprefix("*.").rstrip(".")
                if host and host != domain.lower() and host.endswith(suffix):
                    found.add(host)
        return sorted(found)

    return []
