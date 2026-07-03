"""SSRF guard: refuse to fetch hosts that resolve to non-public addresses.

The crawler follows URLs from untrusted sources — crawled links, @font-face
src, HTTP redirects, and Certificate-Transparency results. Without this, a
target (or a compromised third-party asset it references) could redirect the
crawler at cloud metadata (169.254.169.254), the loopback API, or the internal
network. Resolution is injected so tests stay offline.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import Any

# getaddrinfo-shaped resolver: (host, port, ...) -> list of addrinfo tuples.
Resolver = Callable[..., list[Any]]


def _addr_is_public(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_host(host: str, *, resolver: Resolver = socket.getaddrinfo) -> bool:
    """True only if `host` resolves and every resolved address is public.

    A resolution failure or any non-public address makes the host unsafe (fail
    closed), which also blunts DNS-rebinding since callers re-check per hop.
    """

    if not host:
        return False
    try:
        infos = resolver(host, None)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        sockaddr = info[-1]
        if not isinstance(sockaddr, tuple) or not sockaddr:
            return False
        if not _addr_is_public(str(sockaddr[0])):
            return False
    return True
