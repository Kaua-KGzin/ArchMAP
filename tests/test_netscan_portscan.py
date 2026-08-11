from __future__ import annotations

from archmap.core.netscan import portscan as netscan_portscan


class _FakeSocket:
    def __init__(
        self,
        *,
        connect_ok: bool,
        recv_data: bytes = b"",
        recv_chunks: list[bytes] | None = None,
    ) -> None:
        self._connect_ok = connect_ok
        self._recv_data = recv_data
        self._recv_chunks = list(recv_chunks) if recv_chunks is not None else None

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

    def close(self) -> None:
        return None

    def recv(self, size: int) -> bytes:
        if self._recv_chunks is not None:
            if not self._recv_chunks:
                return b""
            chunk = self._recv_chunks[0]
            piece, rest = chunk[:size], chunk[size:]
            if rest:
                self._recv_chunks[0] = rest
            else:
                self._recv_chunks.pop(0)
            return piece
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
        "details": None,
        "scripts": [],
        "risk": None,
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
    assert result["details"] is None


def test_scan_port_flags_known_risky_port(monkeypatch) -> None:
    monkeypatch.setattr(
        netscan_portscan.socket, "socket", lambda *a, **k: _FakeSocket(connect_ok=True)
    )
    result = netscan_portscan.scan_port("10.0.0.1", 23, timeout=0.1, fingerprint=False)
    assert result["risk"] == {"level": "high", "reason": "Telnet is unencrypted remote access"}


def test_scan_port_http_extracts_details(monkeypatch) -> None:
    http_response = (
        b"HTTP/1.1 200 OK\r\nServer: TestServer/1.0\r\n\r\n"
        b"<html><head><title>Hello</title></head></html>"
    )
    monkeypatch.setattr(
        netscan_portscan.socket,
        "socket",
        lambda *a, **k: _FakeSocket(connect_ok=True, recv_chunks=[http_response]),
    )

    result = netscan_portscan.scan_port("10.0.0.1", 80, timeout=0.1, fingerprint=True)

    assert result["banner"] == "HTTP/1.1 200 OK"
    assert result["details"] == {"server": "TestServer/1.0", "title": "Hello"}


def test_scan_ports_returns_open_sorted(monkeypatch) -> None:
    def fake_scan_port(ip, port, *, timeout, fingerprint):
        return (
            {"port": port, "protocol": "tcp", "state": "open", "service": "x", "banner": None}
            if port in (22, 80)
            else None
        )

    monkeypatch.setattr(netscan_portscan, "scan_port", fake_scan_port)

    result = netscan_portscan.scan_ports("10.0.0.1", [80, 22, 443], timeout=0.1, fingerprint=False)

    assert [p["port"] for p in result] == [22, 80]


def test_scan_ports_empty() -> None:
    assert netscan_portscan.scan_ports("10.0.0.1", [], timeout=0.1) == []


def test_parse_http_response_extracts_status_server_title() -> None:
    data = (
        b"HTTP/1.1 200 OK\r\n"
        b"Server: nginx/1.18.0\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b"<html><head><title>My Site</title></head><body></body></html>"
    )
    status, details = netscan_portscan._parse_http_response(data)
    assert status == "HTTP/1.1 200 OK"
    assert details == {"server": "nginx/1.18.0", "title": "My Site"}


def test_parse_http_response_empty_data() -> None:
    assert netscan_portscan._parse_http_response(b"") == (None, None)


def test_parse_http_response_no_extra_headers() -> None:
    data = b"HTTP/1.1 403 Forbidden\r\n\r\n"
    status, details = netscan_portscan._parse_http_response(data)
    assert status == "HTTP/1.1 403 Forbidden"
    assert details is None


def test_recv_all_stops_on_empty_chunk() -> None:
    sock = _FakeSocket(connect_ok=True, recv_chunks=[b"hello", b" world"])
    assert netscan_portscan._recv_all(sock, limit=8192) == b"hello world"


def test_recv_all_respects_limit() -> None:
    sock = _FakeSocket(connect_ok=True, recv_chunks=[b"x" * 10])
    assert netscan_portscan._recv_all(sock, limit=5) == b"xxxxx"


def test_maybe_wrap_tls_passthrough_for_non_tls_port() -> None:
    sentinel = object()
    result = netscan_portscan._maybe_wrap_tls(sentinel, "10.0.0.1", 80, 1.0)
    assert result is sentinel


def test_maybe_wrap_tls_wraps_tls_port(monkeypatch) -> None:
    sentinel = object()

    class _FakeWrapped:
        def settimeout(self, _timeout: float) -> None:
            self.timed_out_set = True

    class _FakeContext:
        def wrap_socket(self, sock: object, server_hostname: str) -> _FakeWrapped:
            assert sock is sentinel
            assert server_hostname == "10.0.0.1"
            return _FakeWrapped()

    monkeypatch.setattr(
        netscan_portscan.ssl, "_create_unverified_context", lambda: _FakeContext()
    )

    result = netscan_portscan._maybe_wrap_tls(sentinel, "10.0.0.1", 443, 1.0)
    assert isinstance(result, _FakeWrapped)
