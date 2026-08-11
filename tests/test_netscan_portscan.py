from __future__ import annotations

from archmap.core.netscan import portscan as netscan_portscan


class _FakeSocket:
    def __init__(self, *, connect_ok: bool, recv_data: bytes = b"") -> None:
        self._connect_ok = connect_ok
        self._recv_data = recv_data

    def __enter__(self) -> _FakeSocket:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def settimeout(self, _timeout: float) -> None:
        return None

    def connect_ex(self, _addr: tuple[str, int]) -> int:
        return 0 if self._connect_ok else 1

    def connect(self, _addr: tuple[str, int]) -> None:
        if not self._connect_ok:
            raise OSError("connection refused")

    def sendall(self, _data: bytes) -> None:
        return None

    def recv(self, _size: int) -> bytes:
        return self._recv_data


def test_scan_port_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        netscan_portscan.socket, "socket", lambda *a, **k: _FakeSocket(connect_ok=False)
    )
    assert netscan_portscan.scan_port("10.0.0.1", 22, timeout=0.1, fingerprint=False) is None


def test_scan_port_open_without_fingerprint(monkeypatch) -> None:
    monkeypatch.setattr(
        netscan_portscan.socket, "socket", lambda *a, **k: _FakeSocket(connect_ok=True)
    )
    result = netscan_portscan.scan_port("10.0.0.1", 22, timeout=0.1, fingerprint=False)
    assert result == {
        "port": 22,
        "protocol": "tcp",
        "state": "open",
        "service": "ssh",
        "banner": None,
    }


def test_scan_port_open_with_banner(monkeypatch) -> None:
    monkeypatch.setattr(
        netscan_portscan.socket,
        "socket",
        lambda *a, **k: _FakeSocket(connect_ok=True, recv_data=b"SSH-2.0-OpenSSH_9.0\r\n"),
    )
    result = netscan_portscan.scan_port("10.0.0.1", 22, timeout=0.1, fingerprint=True)
    assert result is not None
    assert result["banner"] == "SSH-2.0-OpenSSH_9.0"


def test_scan_ports_returns_open_sorted(monkeypatch) -> None:
    def fake_scan_port(ip, port, *, timeout, fingerprint):
        return {"port": port, "protocol": "tcp", "state": "open", "service": "x", "banner": None} \
            if port in (22, 80) else None

    monkeypatch.setattr(netscan_portscan, "scan_port", fake_scan_port)

    result = netscan_portscan.scan_ports("10.0.0.1", [80, 22, 443], timeout=0.1, fingerprint=False)

    assert [p["port"] for p in result] == [22, 80]


def test_scan_ports_empty() -> None:
    assert netscan_portscan.scan_ports("10.0.0.1", [], timeout=0.1) == []
