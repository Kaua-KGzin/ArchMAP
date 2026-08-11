from __future__ import annotations

import re
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from archmap.core.netscan.ports import service_name
from archmap.core.netscan.risk import classify_port

_HTTP_PORTS = {80, 443, 8000, 8008, 8080, 8081, 8443, 8888, 3000, 4000, 5000, 9000}
_TLS_PORTS = {443, 8443, 465, 993, 995, 636, 990}

_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SERVER_HEADER_RE = re.compile(rb"^Server:[ \t]*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _maybe_wrap_tls(sock: socket.socket, ip: str, port: int, timeout: float):
    if port not in _TLS_PORTS:
        return sock
    context = ssl._create_unverified_context()
    wrapped = context.wrap_socket(sock, server_hostname=ip)
    wrapped.settimeout(timeout)
    return wrapped


def _recv_all(sock, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while total < limit:
            chunk = sock.recv(min(4096, limit - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except OSError:
        pass
    return b"".join(chunks)


def _parse_http_response(data: bytes) -> tuple[str | None, dict[str, str] | None]:
    if not data:
        return None, None

    head = data.split(b"\r\n\r\n", 1)[0]
    first_line = head.split(b"\r\n", 1)[0].decode("utf-8", errors="replace").strip()
    status_line = first_line or None

    details: dict[str, str] = {}
    server_match = _SERVER_HEADER_RE.search(head)
    if server_match:
        details["server"] = server_match.group(1).decode("utf-8", errors="replace")

    title_match = _TITLE_RE.search(data)
    if title_match:
        title = " ".join(title_match.group(1).decode("utf-8", errors="replace").split())[:120]
        if title:
            details["title"] = title

    return status_line, (details or None)


def _probe_service(
    ip: str, port: int, timeout: float
) -> tuple[str | None, dict[str, str] | None]:
    raw_sock = None
    sock = None
    try:
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(timeout)
        raw_sock.connect((ip, port))
        sock = _maybe_wrap_tls(raw_sock, ip, port, timeout)

        if port in _HTTP_PORTS:
            request = (
                f"GET / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: archmap-netscan\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            sock.sendall(request)
            return _parse_http_response(_recv_all(sock, limit=8192))

        data = sock.recv(256)
        if not data:
            return None, None
        text = data.decode("utf-8", errors="replace").strip()
        return (text.splitlines()[0][:200] if text else None), None
    except OSError:
        return None, None
    finally:
        if sock is not None:
            sock.close()
        elif raw_sock is not None:
            raw_sock.close()


def scan_port(ip: str, port: int, *, timeout: float, fingerprint: bool) -> dict[str, Any] | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            is_open = sock.connect_ex((ip, port)) == 0
    except OSError:
        is_open = False

    if not is_open:
        return None

    entry: dict[str, Any] = {
        "port": port,
        "protocol": "tcp",
        "state": "open",
        "service": service_name(port),
        "banner": None,
        "details": None,
        "scripts": [],
        "risk": classify_port(port),
    }
    if fingerprint:
        entry["banner"], entry["details"] = _probe_service(ip, port, timeout)

    return entry


def scan_ports(
    ip: str,
    ports: list[int],
    *,
    timeout: float = 1.0,
    concurrency: int = 200,
    fingerprint: bool = True,
) -> list[dict[str, Any]]:
    if not ports:
        return []

    open_ports: list[dict[str, Any]] = []
    workers = max(1, min(concurrency, len(ports)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(scan_port, ip, port, timeout=timeout, fingerprint=fingerprint)
            for port in ports
        ]
        for future in futures:
            result = future.result()
            if result is not None:
                open_ports.append(result)

    open_ports.sort(key=lambda entry: entry["port"])
    return open_ports
