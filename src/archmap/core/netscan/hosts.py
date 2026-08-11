from __future__ import annotations

import ipaddress
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# A handful of commonly-open ports used as a fallback "is this host alive"
# probe when ICMP ping is unavailable or blocked (common on locked-down
# networks and some mobile carriers).
_DISCOVERY_PROBE_PORTS = (80, 443, 22, 445, 3389, 8080)


def parse_targets(spec: str) -> list[str]:
    """Expand a target spec into a flat, de-duplicated list of hosts.

    Supports comma-separated combinations of:
      - a single IP or hostname ("192.168.1.10", "example.com")
      - a CIDR block ("192.168.1.0/24")
      - a dash range, either full ("192.168.1.1-192.168.1.50") or
        last-octet shorthand ("192.168.1.1-50")
    """
    hosts: list[str] = []
    seen: set[str] = set()

    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for host in _expand_chunk(chunk):
            if host not in seen:
                seen.add(host)
                hosts.append(host)

    return hosts


def _expand_chunk(chunk: str) -> list[str]:
    if "/" in chunk:
        network = ipaddress.ip_network(chunk, strict=False)
        if network.num_addresses > 65536:
            raise ValueError(
                f"refusing to expand {chunk}: {network.num_addresses} addresses "
                "is too large for a single scan"
            )
        hosts = [str(ip) for ip in network.hosts()]
        return hosts or [str(network.network_address)]

    if "-" in chunk and not _looks_like_hostname(chunk):
        start_str, _, end_str = chunk.partition("-")
        start_str = start_str.strip()
        end_str = end_str.strip()
        if "." in end_str:
            start_ip = ipaddress.ip_address(start_str)
            end_ip = ipaddress.ip_address(end_str)
        else:
            start_ip = ipaddress.ip_address(start_str)
            prefix = start_str.rsplit(".", 1)[0]
            end_ip = ipaddress.ip_address(f"{prefix}.{int(end_str)}")

        if int(end_ip) < int(start_ip):
            raise ValueError(f"invalid range {chunk}: end is before start")
        span = int(end_ip) - int(start_ip) + 1
        if span > 65536:
            raise ValueError(f"refusing to expand {chunk}: range too large for a single scan")
        return [str(ipaddress.ip_address(int(start_ip) + i)) for i in range(span)]

    return [chunk]


def _looks_like_hostname(value: str) -> bool:
    try:
        ipaddress.ip_address(value.split("-", 1)[0])
        return False
    except ValueError:
        return True


def resolve_host(host: str) -> str | None:
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def _ping_available() -> bool:
    return shutil.which("ping") is not None


def _ping_once(ip: str, timeout: float) -> bool:
    wait = max(1, int(round(timeout)))
    flags = (
        ["-c", "1", "-t", str(wait)]
        if sys.platform == "darwin"
        else ["-c", "1", "-W", str(wait)]
    )
    try:
        result = subprocess.run(
            ["ping", *flags, ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _tcp_probe_alive(ip: str, timeout: float) -> bool:
    for port in _DISCOVERY_PROBE_PORTS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                if sock.connect_ex((ip, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def is_host_alive(ip: str, *, timeout: float = 1.0, use_ping: bool = True) -> bool:
    """Best-effort liveness check without requiring root.

    Tries ICMP ping first (works unprivileged on Linux/Termux in most
    setups), then falls back to TCP connect probes on common ports, since
    ICMP is frequently filtered on real networks anyway.
    """
    if use_ping and _ping_available() and _ping_once(ip, timeout):
        return True
    return _tcp_probe_alive(ip, timeout)


def discover_hosts(
    ips: list[str],
    *,
    timeout: float = 1.0,
    concurrency: int = 100,
    use_ping: bool = True,
) -> list[str]:
    """Return the subset of `ips` that respond to a liveness check, in input order."""
    if not ips:
        return []

    alive: dict[str, bool] = {}
    workers = max(1, min(concurrency, len(ips)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(is_host_alive, ip, timeout=timeout, use_ping=use_ping): ip for ip in ips
        }
        for future in futures:
            ip = futures[future]
            try:
                alive[ip] = future.result()
            except Exception:  # noqa: BLE001
                alive[ip] = False

    return [ip for ip in ips if alive.get(ip)]


def reverse_lookup(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None
