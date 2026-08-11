from __future__ import annotations

import pytest

from archmap.core.netscan import hosts as netscan_hosts


def test_parse_targets_single_ip() -> None:
    assert netscan_hosts.parse_targets("192.168.1.10") == ["192.168.1.10"]


def test_parse_targets_hostname() -> None:
    assert netscan_hosts.parse_targets("example.com") == ["example.com"]


def test_parse_targets_cidr() -> None:
    result = netscan_hosts.parse_targets("192.168.1.0/30")
    assert result == ["192.168.1.1", "192.168.1.2"]


def test_parse_targets_shorthand_range() -> None:
    result = netscan_hosts.parse_targets("192.168.1.1-3")
    assert result == ["192.168.1.1", "192.168.1.2", "192.168.1.3"]


def test_parse_targets_full_range() -> None:
    result = netscan_hosts.parse_targets("10.0.0.1-10.0.0.2")
    assert result == ["10.0.0.1", "10.0.0.2"]


def test_parse_targets_comma_separated_and_dedup() -> None:
    result = netscan_hosts.parse_targets("192.168.1.1,192.168.1.1,192.168.1.2")
    assert result == ["192.168.1.1", "192.168.1.2"]


def test_parse_targets_rejects_huge_cidr() -> None:
    with pytest.raises(ValueError):
        netscan_hosts.parse_targets("10.0.0.0/8")


def test_parse_targets_rejects_backwards_range() -> None:
    with pytest.raises(ValueError):
        netscan_hosts.parse_targets("192.168.1.10-5")


def test_resolve_host_passes_through_ip() -> None:
    assert netscan_hosts.resolve_host("192.168.1.1") == "192.168.1.1"


def test_resolve_host_returns_none_for_bad_hostname() -> None:
    assert netscan_hosts.resolve_host("this-host-does-not-exist.invalid") is None


def test_discover_hosts_filters_to_alive(monkeypatch) -> None:
    alive_ips = {"10.0.0.1", "10.0.0.3"}
    monkeypatch.setattr(
        netscan_hosts, "is_host_alive", lambda ip, **_kw: ip in alive_ips
    )

    result = netscan_hosts.discover_hosts(
        ["10.0.0.1", "10.0.0.2", "10.0.0.3"], timeout=0.1, concurrency=10
    )

    assert result == ["10.0.0.1", "10.0.0.3"]


def test_discover_hosts_empty_input() -> None:
    assert netscan_hosts.discover_hosts([]) == []


def test_is_host_alive_falls_back_to_tcp_probe(monkeypatch) -> None:
    monkeypatch.setattr(netscan_hosts, "_ping_available", lambda: False)
    monkeypatch.setattr(netscan_hosts, "_tcp_probe_alive", lambda ip, timeout: True)

    assert netscan_hosts.is_host_alive("10.0.0.5", timeout=0.1) is True
