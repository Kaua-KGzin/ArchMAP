from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archmap.core.exposure.network_view import build_network_view
from archmap.core.exposure.snapshots import save_snapshot, snapshot_dir


def _netscan(ports: list[tuple[str, int, str, str | None]]) -> dict[str, Any]:
    hosts: dict[str, dict[str, Any]] = {}
    for ip, port, service, risk in ports:
        hosts.setdefault(ip, {"ip": ip, "hostname": None, "openPorts": []})["openPorts"].append(
            {
                "port": port,
                "protocol": "tcp",
                "service": service,
                "risk": {"level": risk, "reason": "because"} if risk else None,
            }
        )
    return {"target": "10.0.0.0/24", "engine": "python", "hosts": list(hosts.values())}


_DRIFT = {
    "source": "src/app.py",
    "target": "redis",
    "kind": "forbid",
    "rule": "app -> redis",
    "message": "app -> redis is forbidden but src/app.py depends on redis",
}

_EXPOSE = {
    "target": "10.0.0.5",
    "projectRoot": "/app",
    "findings": [
        {
            "id": "NET-001",
            "host": "10.0.0.5",
            "hostname": "web.local",
            "port": 80,
            "protocol": "tcp",
            "service": "http",
            "networkRisk": None,
            "severity": "low",
            "confidence": 0.4,
            "driftViolation": None,
        },
        {
            "id": "NET-002",
            "host": "10.0.0.5",
            "hostname": "web.local",
            "port": 6379,
            "protocol": "tcp",
            "service": "redis",
            "networkRisk": {"level": "high", "reason": "no auth"},
            "severity": "high",
            "confidence": 0.95,
            "driftViolation": _DRIFT,
        },
    ],
    "driftViolations": [_DRIFT],
}


def _save(root: Path, report: dict[str, Any], minute: int) -> None:
    save_snapshot(root, report, captured_at=datetime(2026, 11, 1, 12, minute, tzinfo=UTC))


def test_no_snapshot_is_unavailable_with_a_hint(tmp_path: Path) -> None:
    view = build_network_view(tmp_path)

    assert view["available"] is False
    assert "--snapshot" in view["hint"]
    assert view["snapshots"] == []


def test_latest_expose_snapshot_lists_ports_findings_and_drift(tmp_path: Path) -> None:
    _save(tmp_path, _EXPOSE, 0)

    view = build_network_view(tmp_path)

    assert view["available"] is True
    assert view["latest"]["kind"] == "expose"
    assert view["latest"]["capturedAt"] == "2026-11-01T12:00:00Z"
    assert view["diff"] is None  # only one snapshot: nothing to compare against
    assert view["summary"] == {
        "hosts": 1,
        "openPorts": 2,
        "notable": 1,
        "driftViolations": 1,
        "portsOpened": 0,
        "portsClosed": 0,
    }
    # Most urgent first: the drift-violating, high-severity redis port.
    first = view["ports"][0]
    assert (first["port"], first["id"], first["notable"]) == (6379, "NET-002", True)
    assert first["drift"] == _DRIFT["message"]
    assert view["ports"][1]["id"] == "NET-001"
    assert view["driftViolations"] == [_DRIFT]


def test_diff_against_previous_marks_new_and_closed_ports(tmp_path: Path) -> None:
    _save(tmp_path, _netscan([("10.0.0.5", 22, "ssh", None), ("10.0.0.5", 80, "http", None)]), 0)
    _save(
        tmp_path,
        _netscan([("10.0.0.5", 80, "http", None), ("10.0.0.9", 23, "telnet", "high")]),
        5,
    )

    view = build_network_view(tmp_path)

    assert len(view["snapshots"]) == 2
    assert view["diff"]["from"]["capturedAt"] == "2026-11-01T12:00:00Z"
    by_port = {p["port"]: p for p in view["ports"]}
    assert by_port[23]["isNew"] is True
    assert by_port[80]["isNew"] is False
    assert [p["port"] for p in view["closedPorts"]] == [22]
    assert view["summary"]["portsOpened"] == 1
    assert view["summary"]["portsClosed"] == 1
    assert view["summary"]["notable"] == 1  # telnet, high risk
    assert view["ports"][0]["port"] == 23  # notable sorts first


def test_corrupt_newest_snapshot_is_skipped_for_the_last_good_one(tmp_path: Path) -> None:
    _save(tmp_path, _EXPOSE, 0)
    _save(tmp_path, _EXPOSE, 5)
    newest = sorted(snapshot_dir(tmp_path).glob("*.json"))[-1]
    newest.write_text("{ not json", encoding="utf-8")

    view = build_network_view(tmp_path)

    assert view["available"] is True
    assert view["latest"]["capturedAt"] == "2026-11-01T12:00:00Z"


def test_snapshot_that_vanishes_after_listing_reports_error(tmp_path: Path, monkeypatch) -> None:
    _save(tmp_path, _EXPOSE, 0)

    def boom(_path: Any) -> Any:
        raise OSError("gone")

    monkeypatch.setattr("archmap.core.exposure.network_view.load_snapshot", boom)
    view = build_network_view(tmp_path)

    assert view["available"] is False
    assert "gone" in view["error"]


def test_port_list_is_capped_but_summary_counts_everything(tmp_path: Path) -> None:
    ports = [("10.0.0.5", 1000 + i, "unknown", None) for i in range(30)]
    _save(tmp_path, _netscan(ports), 0)

    view = build_network_view(tmp_path, max_ports=10)

    assert len(view["ports"]) == 10
    assert view["truncated"] is True
    assert view["summary"]["openPorts"] == 30
