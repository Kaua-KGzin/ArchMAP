from __future__ import annotations

from typing import Any

from archmap.core.exposure.network_diff import (
    diff_network_snapshots,
    normalize_hosts,
    normalize_observations,
)
from archmap.core.exposure.snapshots import Snapshot


def _snapshot(report: dict[str, Any], *, kind: str = "netscan", captured: str = "") -> Snapshot:
    return {
        "version": 1,
        "kind": kind,
        "target": str(report.get("target", "")),
        "capturedAt": captured or "2026-08-01T12:00:00Z",
        "report": report,
    }


def _netscan(hosts: list[dict[str, Any]], target: str = "192.168.1.0/24") -> dict[str, Any]:
    return {"target": target, "engine": "python", "hosts": hosts}


def _host(ip: str, ports: list[dict[str, Any]], hostname: str | None = None) -> dict[str, Any]:
    return {"ip": ip, "hostname": hostname, "openPorts": ports}


def _port(port: int, service: str = "unknown", risk: str | None = None) -> dict[str, Any]:
    return {
        "port": port,
        "protocol": "tcp",
        "service": service,
        "risk": {"level": risk, "reason": "because"} if risk else None,
    }


_EXPOSE = {
    "target": "192.168.1.10",
    "projectRoot": "/app",
    "findings": [
        {
            "host": "192.168.1.10",
            "hostname": "db.local",
            "port": 6379,
            "protocol": "tcp",
            "service": "redis",
            "networkRisk": {"level": "high", "reason": "no auth"},
            "severity": "high",
            "confidence": 0.95,
            "driftViolation": {
                "source": "src/app.py",
                "target": "redis",
                "kind": "forbid",
                "rule": "app -> redis",
                "message": "app -> redis is forbidden but src/app.py depends on redis",
            },
        }
    ],
    "driftViolations": [
        {
            "source": "src/app.py",
            "target": "redis",
            "kind": "forbid",
            "rule": "app -> redis",
            "message": "app -> redis is forbidden but src/app.py depends on redis",
        }
    ],
}


def test_normalize_observations_reads_a_netscan_host_tree():
    report = _netscan([_host("192.168.1.10", [_port(5432, "postgresql", "medium")], "db.local")])

    assert normalize_observations(report) == [
        {
            "host": "192.168.1.10",
            "hostname": "db.local",
            "port": 5432,
            "protocol": "tcp",
            "service": "postgresql",
            "riskLevel": "medium",
            "severity": None,
            "confidence": None,
            "drift": None,
        }
    ]


def test_normalize_observations_reads_an_expose_findings_list():
    observations = normalize_observations(_EXPOSE)

    assert len(observations) == 1
    assert observations[0]["service"] == "redis"
    assert observations[0]["severity"] == "high"
    assert observations[0]["confidence"] == 0.95
    assert observations[0]["drift"] is not None


def test_normalize_observations_is_sorted_deterministically():
    report = _netscan(
        [
            _host("192.168.1.20", [_port(80), _port(22)]),
            _host("192.168.1.10", [_port(443)]),
        ]
    )

    assert [(o["host"], o["port"]) for o in normalize_observations(report)] == [
        ("192.168.1.10", 443),
        ("192.168.1.20", 22),
        ("192.168.1.20", 80),
    ]


def test_normalize_hosts_keeps_live_hosts_with_no_open_ports():
    report = _netscan([_host("192.168.1.10", []), _host("192.168.1.20", [_port(22)])])

    assert normalize_hosts(report) == [
        {"host": "192.168.1.10", "hostname": None},
        {"host": "192.168.1.20", "hostname": None},
    ]


def test_normalize_hosts_derives_hosts_from_expose_findings():
    assert normalize_hosts(_EXPOSE) == [{"host": "192.168.1.10", "hostname": "db.local"}]


def test_diff_reports_ports_opened_and_closed():
    before = _snapshot(_netscan([_host("192.168.1.10", [_port(22, "ssh")])]))
    after = _snapshot(_netscan([_host("192.168.1.10", [_port(6379, "redis", "high")])]))

    result = diff_network_snapshots(before, after)

    assert [o["port"] for o in result["portsOpened"]] == [6379]
    assert [o["port"] for o in result["portsClosed"]] == [22]
    assert result["summary"]["changed"] is True


def test_diff_reports_service_and_risk_changes_on_a_port_that_stayed_open():
    before = _snapshot(_netscan([_host("192.168.1.10", [_port(8080, "http")])]))
    after = _snapshot(_netscan([_host("192.168.1.10", [_port(8080, "http-proxy", "medium")])]))

    result = diff_network_snapshots(before, after)

    assert result["portsOpened"] == []
    assert result["serviceChanges"] == [
        {
            "host": "192.168.1.10",
            "hostname": None,
            "port": 8080,
            "protocol": "tcp",
            "field": "service",
            "from": "http",
            "to": "http-proxy",
        }
    ]
    assert result["riskChanges"][0]["from"] is None
    assert result["riskChanges"][0]["to"] == "medium"


def test_diff_reports_hosts_appearing_and_disappearing():
    before = _snapshot(_netscan([_host("192.168.1.10", [])]))
    after = _snapshot(_netscan([_host("192.168.1.30", [], "new.local")]))

    result = diff_network_snapshots(before, after)

    assert result["hostsAppeared"] == [{"host": "192.168.1.30", "hostname": "new.local"}]
    assert result["hostsDisappeared"] == [{"host": "192.168.1.10", "hostname": None}]


def test_diff_reports_new_and_resolved_drift_violations():
    clean = _snapshot({"target": "192.168.1.10", "findings": [], "driftViolations": []})
    dirty = _snapshot(_EXPOSE, kind="expose")

    appeared = diff_network_snapshots(clean, dirty)
    assert appeared["summary"]["driftViolationsNew"] == 1
    assert appeared["driftViolationsNew"][0]["rule"] == "app -> redis"

    resolved = diff_network_snapshots(dirty, clean)
    assert resolved["summary"]["driftViolationsResolved"] == 1
    assert resolved["driftViolationsNew"] == []


def test_identical_snapshots_report_no_change():
    snapshot = _snapshot(_netscan([_host("192.168.1.10", [_port(22, "ssh")])]))

    result = diff_network_snapshots(snapshot, snapshot)

    assert result["summary"]["changed"] is False
    assert all(result[key] == [] for key in ("portsOpened", "portsClosed", "serviceChanges"))


def test_diff_does_not_mutate_either_snapshot():
    before_report = _netscan([_host("192.168.1.10", [_port(22, "ssh")])])
    after_report = _netscan([_host("192.168.1.10", [_port(80, "http")])])
    before_copy = _netscan([_host("192.168.1.10", [_port(22, "ssh")])])
    after_copy = _netscan([_host("192.168.1.10", [_port(80, "http")])])

    diff_network_snapshots(_snapshot(before_report), _snapshot(after_report))

    assert before_report == before_copy
    assert after_report == after_copy


def test_a_netscan_snapshot_diffs_cleanly_against_an_expose_snapshot():
    before = _snapshot(_netscan([_host("192.168.1.10", [_port(6379, "redis", "high")])]))
    after = _snapshot(_EXPOSE, kind="expose")

    result = diff_network_snapshots(before, after)

    # Same host:port in both shapes — no phantom open/close from the reshaping.
    assert result["portsOpened"] == []
    assert result["portsClosed"] == []
    assert result["summary"]["driftViolationsNew"] == 1


def test_diff_carries_both_snapshots_metadata():
    before = _snapshot(_netscan([]), captured="2026-08-01T12:00:00Z")
    after = _snapshot(_EXPOSE, kind="expose", captured="2026-08-13T12:00:00Z")

    result = diff_network_snapshots(before, after)

    assert result["from"]["capturedAt"] == "2026-08-01T12:00:00Z"
    assert result["to"] == {
        "kind": "expose",
        "target": "192.168.1.10",
        "capturedAt": "2026-08-13T12:00:00Z",
    }


def test_observations_without_a_port_are_skipped():
    report = {"target": "10.0.0.1", "findings": [{"host": "10.0.0.1", "service": "unknown"}]}

    assert normalize_observations(report) == []
