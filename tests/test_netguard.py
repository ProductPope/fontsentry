"""SSRF guard: only public addresses are fetchable (resolver injected, offline)."""

from __future__ import annotations

from typing import Any

import pytest

from fontsentry.crawl.netguard import is_safe_host


def _resolver(*ips: str) -> Any:
    def resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
        return [(2, 1, 6, "", (ip, 0)) for ip in ips]

    return resolve


def test_public_address_is_safe() -> None:
    assert is_safe_host("example.com", resolver=_resolver("93.184.216.34")) is True


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"])
def test_non_public_addresses_blocked(ip: str) -> None:
    assert is_safe_host("evil.test", resolver=_resolver(ip)) is False


def test_any_non_public_in_the_set_blocks() -> None:
    # Public + private (DNS returning multiple A records) -> unsafe.
    assert is_safe_host("mixed.test", resolver=_resolver("93.184.216.34", "127.0.0.1")) is False


def test_resolution_failure_fails_closed() -> None:
    def boom(*a: Any, **k: Any) -> list[Any]:
        raise OSError("nxdomain")

    assert is_safe_host("nope.test", resolver=boom) is False


def test_empty_host_is_unsafe() -> None:
    assert is_safe_host("", resolver=_resolver("93.184.216.34")) is False
