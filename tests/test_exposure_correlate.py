from __future__ import annotations

from archmap.core.exposure.correlate import correlate_exposure


def _netscan_report(*ports: dict) -> dict:
    return {
        "target": "192.168.1.10",
        "hosts": [
            {
                "ip": "192.168.1.10",
                "hostname": None,
                "openPorts": list(ports),
            }
        ],
    }


def _package_node(name: str, *, impact_count: int, risk: str) -> dict:
    return {
        "id": f"pkg:{name}",
        "label": name,
        "type": "package",
        "impact": {
            "nodeId": f"pkg:{name}",
            "impactCount": impact_count,
            "impactedFiles": [f"file_{i}.py" for i in range(impact_count)],
            "risk": risk,
        },
    }


def test_correlate_matches_package_and_combines_severity() -> None:
    netscan_report = _netscan_report(
        {
            "port": 6379,
            "protocol": "tcp",
            "service": "redis",
            "risk": {"level": "high", "reason": "Redis often runs unauthenticated"},
        }
    )
    analysis_report = {
        "projectRoot": "/app",
        "nodes": [_package_node("redis", impact_count=12, risk="critical")],
    }

    result = correlate_exposure(netscan_report, analysis_report)

    assert result["target"] == "192.168.1.10"
    assert result["projectRoot"] == "/app"
    finding = result["findings"][0]
    assert finding["id"] == "NET-001"
    assert finding["category"] == "network_port"
    assert finding["service"] == "redis"
    assert finding["networkRisk"]["level"] == "high"
    assert finding["matchedPackages"][0]["package"] == "redis"
    assert finding["matchedPackages"][0]["impactCount"] == 12
    assert finding["severity"] == "critical"
    assert result["summary"] == {
        "openPorts": 1,
        "matchedToCode": 1,
        "highSeverity": 1,
        "driftViolations": 0,
    }


def test_correlate_no_code_match_keeps_network_severity() -> None:
    netscan_report = _netscan_report(
        {
            "port": 23,
            "protocol": "tcp",
            "service": "telnet",
            "risk": {"level": "high", "reason": "Telnet is unencrypted"},
        }
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}

    result = correlate_exposure(netscan_report, analysis_report)

    finding = result["findings"][0]
    assert finding["matchedPackages"] == []
    assert finding["severity"] == "high"
    assert result["summary"]["matchedToCode"] == 0


def test_correlate_no_signal_is_info_severity() -> None:
    netscan_report = _netscan_report(
        {"port": 80, "protocol": "tcp", "service": "http", "risk": None}
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}

    result = correlate_exposure(netscan_report, analysis_report)

    finding = result["findings"][0]
    assert finding["severity"] == "info"
    assert finding["networkRisk"] is None


def test_correlate_code_match_without_network_risk_uses_code_severity() -> None:
    netscan_report = _netscan_report(
        {"port": 5672, "protocol": "tcp", "service": "amqp", "risk": None}
    )
    analysis_report = {
        "projectRoot": "/app",
        "nodes": [_package_node("pika", impact_count=8, risk="warning")],
    }

    result = correlate_exposure(netscan_report, analysis_report)

    finding = result["findings"][0]
    assert finding["matchedPackages"][0]["package"] == "pika"
    assert finding["severity"] == "medium"


def test_correlate_ignores_file_nodes() -> None:
    netscan_report = _netscan_report(
        {"port": 6379, "protocol": "tcp", "service": "redis", "risk": None}
    )
    analysis_report = {
        "projectRoot": "/app",
        "nodes": [
            {
                "id": "redis",
                "label": "redis",
                "type": "file",
                "impact": {
                    "nodeId": "redis",
                    "impactCount": 99,
                    "impactedFiles": [],
                    "risk": "critical",
                },
            }
        ],
    }

    result = correlate_exposure(netscan_report, analysis_report)

    assert result["findings"][0]["matchedPackages"] == []


def test_correlate_includes_every_open_port() -> None:
    netscan_report = _netscan_report(
        {"port": 80, "protocol": "tcp", "service": "http", "risk": None},
        {"port": 443, "protocol": "tcp", "service": "https", "risk": None},
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}

    result = correlate_exposure(netscan_report, analysis_report)

    assert len(result["findings"]) == 2
    assert result["summary"]["openPorts"] == 2


def test_correlate_endpoint_match_gives_high_confidence() -> None:
    netscan_report = _netscan_report(
        {"port": 6379, "protocol": "tcp", "service": "redis", "risk": None}
    )
    analysis_report = {
        "projectRoot": "/app",
        "nodes": [_package_node("redis", impact_count=3, risk="ok")],
    }
    endpoint_refs = [
        {"file": "src/cache.py", "host": "192.168.1.10", "port": 6379, "service": "redis"}
    ]

    result = correlate_exposure(netscan_report, analysis_report, endpoint_refs)

    finding = result["findings"][0]
    assert finding["confidence"] == 0.95
    assert "src/cache.py" in finding["confidenceReasons"][0]


def test_correlate_package_only_match_gives_low_confidence() -> None:
    netscan_report = _netscan_report(
        {"port": 6379, "protocol": "tcp", "service": "redis", "risk": None}
    )
    analysis_report = {
        "projectRoot": "/app",
        "nodes": [_package_node("redis", impact_count=3, risk="ok")],
    }

    result = correlate_exposure(netscan_report, analysis_report)

    finding = result["findings"][0]
    assert finding["confidence"] == 0.4


def test_correlate_no_signal_gives_zero_confidence() -> None:
    netscan_report = _netscan_report(
        {"port": 80, "protocol": "tcp", "service": "http", "risk": None}
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}

    result = correlate_exposure(netscan_report, analysis_report)

    finding = result["findings"][0]
    assert finding["confidence"] == 0.0
    assert finding["confidenceReasons"] == []


def test_correlate_endpoint_service_mismatch_lowers_confidence() -> None:
    netscan_report = _netscan_report(
        {"port": 6379, "protocol": "tcp", "service": "redis", "risk": None}
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}
    endpoint_refs = [
        {"file": "src/queue.py", "host": "192.168.1.10", "port": 6379, "service": "amqp"}
    ]

    result = correlate_exposure(netscan_report, analysis_report, endpoint_refs)

    finding = result["findings"][0]
    assert finding["confidence"] == 0.7
    assert len(finding["confidenceReasons"]) == 2


def test_correlate_flags_drift_violation_for_forbidden_rule() -> None:
    netscan_report = _netscan_report(
        {"port": 5432, "protocol": "tcp", "service": "postgresql", "risk": None}
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}
    endpoint_refs = [
        {
            "file": "src/frontend/widget.py",
            "host": "192.168.1.10",
            "port": 5432,
            "service": "postgresql",
        }
    ]
    network_rules = {"forbid": ["frontend -> postgresql"], "allow": []}

    result = correlate_exposure(netscan_report, analysis_report, endpoint_refs, network_rules)

    finding = result["findings"][0]
    assert finding["id"] == "NET-001"
    assert finding["category"] == "network_drift"
    assert finding["driftViolation"] is not None
    assert finding["severity"] == "high"
    assert result["summary"]["driftViolations"] == 1
    assert len(result["driftViolations"]) == 1


def test_correlate_no_drift_when_rule_not_violated() -> None:
    netscan_report = _netscan_report(
        {"port": 5432, "protocol": "tcp", "service": "postgresql", "risk": None}
    )
    analysis_report = {"projectRoot": "/app", "nodes": []}
    endpoint_refs = [
        {
            "file": "src/backend/db.py",
            "host": "192.168.1.10",
            "port": 5432,
            "service": "postgresql",
        }
    ]
    network_rules = {"forbid": ["frontend -> postgresql"], "allow": []}

    result = correlate_exposure(netscan_report, analysis_report, endpoint_refs, network_rules)

    finding = result["findings"][0]
    assert finding["driftViolation"] is None
    assert result["summary"]["driftViolations"] == 0


def test_correlate_no_open_ports() -> None:
    netscan_report = {"target": "10.0.0.1", "hosts": [{"ip": "10.0.0.1", "openPorts": []}]}
    analysis_report = {"projectRoot": "/app", "nodes": []}

    result = correlate_exposure(netscan_report, analysis_report)

    assert result["findings"] == []
    assert result["summary"] == {
        "openPorts": 0,
        "matchedToCode": 0,
        "highSeverity": 0,
        "driftViolations": 0,
    }
