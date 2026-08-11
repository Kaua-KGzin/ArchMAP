from __future__ import annotations

from archmap.core.netscan import risk


def test_classify_port_known_high_risk() -> None:
    result = risk.classify_port(23)
    assert result == {"level": "high", "reason": "Telnet is unencrypted remote access"}


def test_classify_port_known_critical_risk() -> None:
    result = risk.classify_port(2375)
    assert result["level"] == "critical"


def test_classify_port_unknown_returns_none() -> None:
    assert risk.classify_port(65000) is None
    assert risk.classify_port(80) is None
