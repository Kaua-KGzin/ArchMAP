from __future__ import annotations

import pytest

from archmap.core.netscan import ports as netscan_ports


def test_parse_ports_explicit_list() -> None:
    assert netscan_ports.parse_ports("22,80,443") == [22, 80, 443]


def test_parse_ports_range() -> None:
    assert netscan_ports.parse_ports("8000-8002") == [8000, 8001, 8002]


def test_parse_ports_mixed() -> None:
    assert netscan_ports.parse_ports("22,80-82") == [22, 80, 81, 82]


def test_parse_ports_backwards_range_normalizes() -> None:
    assert netscan_ports.parse_ports("82-80") == [80, 81, 82]


def test_parse_ports_defaults_to_top_ports() -> None:
    result = netscan_ports.parse_ports(None)
    assert len(result) == 20
    assert result == sorted(result)


def test_parse_ports_respects_top_arg() -> None:
    result = netscan_ports.parse_ports(None, top=5)
    assert len(result) == 5


def test_parse_ports_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        netscan_ports.parse_ports("70000")


def test_service_name_known_and_unknown() -> None:
    assert netscan_ports.service_name(22) == "ssh"
    assert netscan_ports.service_name(65000) == "unknown"
