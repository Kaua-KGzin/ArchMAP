from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from archmap.core.netscan.ports import service_name

_HTTP_PORTS = {80, 443, 8000, 8008, 8080, 8081, 8443, 8888, 3000, 4000, 5000, 9000}


def _grab_banner(ip: str, port: int, timeout: float) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))
            if port in _HTTP_PORTS:
                request = f"HEAD / HTTP/1.0\r\nHost: {ip}\r\n\r\n".encode()
                sock.sendall(request)
            data = sock.recv(256)
            if not data:
                return None
            text = data.decode("utf-8", errors="replace").strip()
            return text.splitlines()[0][:200] if text else None
    except OSError:
        return None


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
    }
    if fingerprint:
        entry["banner"] = _grab_banner(ip, port, timeout)

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
