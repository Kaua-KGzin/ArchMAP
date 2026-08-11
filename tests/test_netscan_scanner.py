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

    result = netscan_scanner.run_netscan("10.0.0.0/30", ports_spec="22", use_nmap=False)

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

    result = netscan_scanner.run_netscan("10.0.0.1", discover_only=True, use_nmap=False)

    assert result["discoverOnly"] is True
    assert result["hosts"][0]["openPorts"] == []


def test_run_netscan_no_discover_scans_every_target(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1", "10.0.0.2"])

    def _fail_discover(*_a, **_k):
        raise AssertionError("discover_hosts should not be called with no_discover=True")

    monkeypatch.setattr(netscan_scanner, "discover_hosts", _fail_discover)
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)
    monkeypatch.setattr(netscan_scanner, "scan_ports", lambda ip, ports, **kw: [])

    result = netscan_scanner.run_netscan(
        "10.0.0.1,10.0.0.2", ports_spec="22", no_discover=True, use_nmap=False
    )

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


def test_run_netscan_auto_uses_nmap_when_available(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "is_nmap_available", lambda: True)
    monkeypatch.setattr(
        netscan_scanner,
        "run_nmap",
        lambda target, ports, **kw: {"engine": "nmap", "hosts": []},
    )

    def _fail_discover(*_a, **_k):
        raise AssertionError("pure-Python discovery should not run when nmap is auto-selected")

    monkeypatch.setattr(netscan_scanner, "discover_hosts", _fail_discover)

    result = netscan_scanner.run_netscan("10.0.0.1", ports_spec="22")

    assert result["engine"] == "nmap"


def test_run_netscan_auto_falls_back_to_python_when_nmap_missing(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "is_nmap_available", lambda: False)
    monkeypatch.setattr(netscan_scanner, "discover_hosts", lambda ips, **kw: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)
    monkeypatch.setattr(netscan_scanner, "scan_ports", lambda ip, ports, **kw: [])

    def _fail_run_nmap(*_a, **_k):
        raise AssertionError("nmap should not be invoked when it isn't available")

    monkeypatch.setattr(netscan_scanner, "run_nmap", _fail_run_nmap)

    result = netscan_scanner.run_netscan("10.0.0.1", ports_spec="22")

    assert result["engine"] == "python"


def test_run_netscan_no_nmap_forces_python_even_when_available(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "is_nmap_available", lambda: True)
    monkeypatch.setattr(netscan_scanner, "discover_hosts", lambda ips, **kw: ["10.0.0.1"])
    monkeypatch.setattr(netscan_scanner, "reverse_lookup", lambda ip: None)
    monkeypatch.setattr(netscan_scanner, "scan_ports", lambda ip, ports, **kw: [])

    def _fail_run_nmap(*_a, **_k):
        raise AssertionError("nmap should not be invoked when use_nmap=False forces Python")

    monkeypatch.setattr(netscan_scanner, "run_nmap", _fail_run_nmap)

    result = netscan_scanner.run_netscan("10.0.0.1", ports_spec="22", use_nmap=False)

    assert result["engine"] == "python"


def test_run_netscan_passes_detect_os_to_nmap(monkeypatch) -> None:
    monkeypatch.setattr(netscan_scanner, "parse_targets", lambda spec: ["10.0.0.1"])
    captured: dict = {}

    def fake_run_nmap(target, ports, **kw):
        captured.update(kw)
        return {"engine": "nmap", "hosts": []}

    monkeypatch.setattr(netscan_scanner, "run_nmap", fake_run_nmap)

    netscan_scanner.run_netscan("10.0.0.1", ports_spec="22", use_nmap=True, detect_os=True)

    assert captured["detect_os"] is True
