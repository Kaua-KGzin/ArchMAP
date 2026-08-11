from __future__ import annotations

import pytest

from archmap.core.netscan import nmap_wrapper

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.0.0.1" addrtype="ipv4"/>
    <hostnames><hostname name="box.local" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="9.0"/>
      </port>
      <port protocol="tcp" portid="23">
        <state state="closed"/>
        <service name="telnet"/>
      </port>
    </ports>
  </host>
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

    result = nmap_wrapper.run_nmap("10.0.0.1", [22, 23])

    assert "-p" in captured_command
    assert result["engine"] == "nmap"
    assert len(result["hosts"]) == 1
    host = result["hosts"][0]
    assert host["ip"] == "10.0.0.1"
    assert host["hostname"] == "box.local"
    assert host["status"] == "up"
    assert host["openPorts"] == [
        {
            "port": 22,
            "protocol": "tcp",
            "state": "open",
            "service": "ssh",
            "banner": "OpenSSH 9.0",
        }
    ]


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
