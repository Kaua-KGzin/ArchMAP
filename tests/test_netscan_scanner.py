from __future__ import annotations

from archmap.core.netscan import scanner as netscan_scanner


def test_run_netscan_pure_python(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1", "10.0.0.2"])
    monkeypatch.setattr(netscan_scanner, "discover_hosts", lambda ips, **kw: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)
    monkeypatch.setattr(
        netscan_scanner,
        "scan_ports",
        lambda ip, ports, **kw: [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh", "banner": None}
        ],
    )

    result = netscan_scanner.run_netscan("10.0.0.0/30", ports_spec="22")

    assert result["target"] == "10.0.0.0/30"
    assert result["engine"] == "python"
    assert result["hostsScanned"] == 2
    assert result["discoverOnly"] is False
    assert len(result["hosts"]) == 1
    assert result["hosts"][0]["ip"] == "10.0.0.1"
    assert result["hosts"][0]["openPorts"][0]["port"] == 22
    assert "durationSeconds" in result


def test_run_netscan_discover_only_skips_port_scan(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "discover_hosts", lambda ips, **kw: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)

    def _fail_scan_ports(*_a, **_k):
        raise AssertionError("scan_ports should not be called in discover-only mode")

    monkeypatch.setattr(netscan_scanner, "scan_ports", _fail_scan_ports)

    result = netscan_scanner.run_netscan("10.0.0.1", discover_only=True)

    assert result["discoverOnly"] is True
    assert result["hosts"][0]["openPorts"] == []


def test_run_netscan_no_discover_scans_every_target(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1", "10.0.0.2"])

    def _fail_discover(*_a, **_k):
        raise AssertionError("discover_hosts should not be called with no_discover=True")

    monkeypatch.setattr(netscan_scanner, "discover_hosts", _fail_discover)
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)
    monkeypatch.setattr(netscan_scanner, "scan_ports", lambda ip, ports, **kw: [])

    result = netscan_scanner.run_netscan("10.0.0.1,10.0.0.2", ports_spec="22", no_discover=True)

    assert [h["ip"] for h in result["hosts"]] == ["10.0.0.1", "10.0.0.2"]


def test_run_netscan_use_nmap_delegates(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    monkeypatch.setattr(
        netscan_scanner,
        "run_nmap",
        lambda target, ports, **kw: {"engine": "nmap", "hosts": [{"ip": "10.0.0.1"}]},
    )

    result = netscan_scanner.run_netscan("10.0.0.1", ports_spec="22", use_nmap=True)

    assert result["engine"] == "nmap"
    assert result["hostsScanned"] == 1
    assert result["discoverOnly"] is False
