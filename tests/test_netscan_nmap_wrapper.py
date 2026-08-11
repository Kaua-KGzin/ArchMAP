from __future__ import annotations

import pytest

from archmap.core.netscan import nmap_wrapper

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun version="7.94">
  <host>
    <status state="up"/>
    <address addr="10.0.0.1" addrtype="ipv4"/>
    <hostnames><hostname name="box.local" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="9.0" extrainfo="protocol 2.0"/>
      </port>
      <port protocol="tcp" portid="23">
        <state state="closed"/>
        <service name="telnet"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http"/>
        <script id="http-title" output="Welcome page"/>
        <script id="http-server-header" output="nginx/1.18.0"/>
      </port>
      <port protocol="tcp" portid="6379">
        <state state="open"/>
        <service name="redis"/>
      </port>
    </ports>
    <hostscript>
      <script id="nbstat" output="  NetBIOS name: BOX"/>
    </hostscript>
    <os>
      <osmatch name="Linux 5.X" accuracy="92"/>
      <osmatch name="Linux 4.X" accuracy="80"/>
    </os>
  </host>
  <runstats>
    <finished time="1700000000" elapsed="11.80"/>
    <hosts up="1" down="253" total="254"/>
  </runstats>
</nmaprun>
"""


def test_is_nmap_available(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper.shutil, "which", lambda _name: "/usr/bin/nmap")
    assert nmap_wrapper.is_nmap_available() is True

    monkeypatch.setattr(nmap_wrapper.shutil, "which", lambda _name: None)
    assert nmap_wrapper.is_nmap_available() is False


def test_run_nmap_raises_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: False)
    with pytest.raises(RuntimeError):
        nmap_wrapper.run_nmap("10.0.0.1", [22])


def test_run_nmap_parses_xml_output(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)

    captured_command: list[str] = []

    class _FakeCompleted:
        returncode = 0
        stdout = SAMPLE_XML.encode()
        stderr = b""

    def fake_run(command, **_kwargs):
        captured_command.extend(command)
        return _FakeCompleted()

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", fake_run)

    result = nmap_wrapper.run_nmap("10.0.0.1", [22, 23, 80, 6379])

    assert "-p" in captured_command
    assert result["engine"] == "nmap"
    assert result["nmapVersion"] == "7.94"
    assert result["stats"] == {"elapsedSeconds": 11.8, "hostsUp": 1, "hostsDown": 253}
    assert len(result["hosts"]) == 1
    host = result["hosts"][0]
    assert host["ip"] == "10.0.0.1"
    assert host["hostname"] == "box.local"
    assert host["status"] == "up"
    assert host["os"] == "Linux 5.X (92%)"
    assert host["scripts"] == [{"id": "nbstat", "output": "NetBIOS name: BOX"}]

    ssh_port, http_port, redis_port = host["openPorts"]
    assert ssh_port == {
        "port": 22,
        "protocol": "tcp",
        "state": "open",
        "service": "ssh",
        "banner": "OpenSSH 9.0 protocol 2.0",
        "details": None,
        "scripts": [],
        "risk": None,
    }
    assert http_port["port"] == 80
    assert http_port["scripts"] == [
        {"id": "http-title", "output": "Welcome page"},
        {"id": "http-server-header", "output": "nginx/1.18.0"},
    ]
    assert redis_port["port"] == 6379
    assert redis_port["risk"] == {
        "level": "high",
        "reason": "Redis is frequently deployed with no authentication",
    }


def test_run_nmap_without_os_or_runstats_omits_optional_fields(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)

    class _FakeCompleted:
        returncode = 0
        stdout = b"<nmaprun></nmaprun>"
        stderr = b""

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", lambda *a, **k: _FakeCompleted())

    result = nmap_wrapper.run_nmap("10.0.0.1", [])

    assert result["nmapVersion"] is None
    assert "stats" not in result
    assert result["hosts"] == []


def test_run_nmap_detect_os_inserts_flag(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)
    captured_command: list[str] = []

    class _FakeCompleted:
        returncode = 0
        stdout = b"<nmaprun></nmaprun>"
        stderr = b""

    def fake_run(command, **_kwargs):
        captured_command.extend(command)
        return _FakeCompleted()

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", fake_run)

    nmap_wrapper.run_nmap("10.0.0.1", [22], detect_os=True)

    assert "-O" in captured_command
    assert captured_command[-1] == "10.0.0.1"


def test_run_nmap_scripts_inserts_sc_and_sv(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)
    captured_command: list[str] = []

    class _FakeCompleted:
        returncode = 0
        stdout = b"<nmaprun></nmaprun>"
        stderr = b""

    def fake_run(command, **_kwargs):
        captured_command.extend(command)
        return _FakeCompleted()

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", fake_run)

    nmap_wrapper.run_nmap("10.0.0.1", [22], scripts=True)

    assert "-sC" in captured_command
    assert "-sV" in captured_command
    assert captured_command[-1] == "10.0.0.1"


def test_run_nmap_uses_ping_scan_when_no_ports(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)
    captured_command: list[str] = []

    class _FakeCompleted:
        returncode = 0
        stdout = b"<nmaprun></nmaprun>"
        stderr = b""

    def fake_run(command, **_kwargs):
        captured_command.extend(command)
        return _FakeCompleted()

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", fake_run)

    nmap_wrapper.run_nmap("10.0.0.1", [])

    assert "-sn" in captured_command
    assert "-p" not in captured_command


def test_run_nmap_raises_on_nonzero_exit(monkeypatch) -> None:
    monkeypatch.setattr(nmap_wrapper, "is_nmap_available", lambda: True)

    class _FakeCompleted:
        returncode = 1
        stdout = b""
        stderr = b"permission denied"

    monkeypatch.setattr(nmap_wrapper.subprocess, "run", lambda *a, **k: _FakeCompleted())

    with pytest.raises(RuntimeError, match="permission denied"):
        nmap_wrapper.run_nmap("10.0.0.1", [22])
