from __future__ import annotations

import time
from typing import Any

from archmap.core.netscan.hosts import discover_hosts, parse_targets, reverse_lookup
from archmap.core.netscan.nmap_wrapper import is_nmap_available, run_nmap
from archmap.core.netscan.ports import parse_ports
from archmap.core.netscan.portscan import scan_ports


def run_netscan(
    target_spec: str,
    *,
    ports_spec: str | None = None,
    top_ports: int | None = None,
    discover_only: bool = False,
    no_discover: bool = False,
    fingerprint: bool = True,
    use_nmap: bool | None = None,
    nmap_args: str | None = None,
    detect_os: bool = False,
    scripts: bool = False,
    timeout: float = 1.0,
    concurrency: int = 200,
) -> dict[str, Any]:
    """Discover live hosts on `target_spec` and, unless --discover-only, scan
    their open ports.

    Uses the system `nmap` binary as the engine whenever it's installed
    (nmap is a far more capable scanner than the built-in one) — pass
    `use_nmap=False` to force the stdlib-only Python engine instead, or
    `use_nmap=True` to require nmap and fail loudly if it's missing.
    """
    started_at = time.time()
    ips = parse_targets(target_spec)
    ports = [] if discover_only else parse_ports(ports_spec, top=top_ports)

    resolved_use_nmap = is_nmap_available() if use_nmap is None else use_nmap

    if resolved_use_nmap:
        result = _run_with_nmap(
            target_spec,
            ips,
            ports,
            nmap_args=nmap_args,
            detect_os=detect_os,
            scripts=scripts,
            timeout=timeout,
        )
    else:
        result = _run_pure_python(
            ips,
            ports,
            discover_only=discover_only,
            no_discover=no_discover,
            fingerprint=fingerprint,
            timeout=timeout,
            concurrency=concurrency,
        )

    result["target"] = target_spec
    result["durationSeconds"] = round(time.time() - started_at, 3)
    return result


def _run_pure_python(
    ips: list[str],
    ports: list[int],
    *,
    discover_only: bool,
    no_discover: bool,
    fingerprint: bool,
    timeout: float,
    concurrency: int,
) -> dict[str, Any]:
    if no_discover:
        live_ips = list(ips)
    else:
        live_ips = discover_hosts(ips, timeout=timeout, concurrency=concurrency)

    hosts: list[dict[str, Any]] = []
    for ip in live_ips:
        open_ports: list[dict[str, Any]] = []
        if not discover_only:
            open_ports = scan_ports(
                ip,
                ports,
                timeout=timeout,
                concurrency=concurrency,
                fingerprint=fingerprint,
            )
        hosts.append(
            {
                "ip": ip,
                "hostname": reverse_lookup(ip),
                "status": "up",
                "os": None,
                "scripts": [],
                "openPorts": open_ports,
            }
        )

    return {
        "engine": "python",
        "hostsScanned": len(ips),
        "discoverOnly": discover_only,
        "hosts": hosts,
    }


def _run_with_nmap(
    target_spec: str,
    ips: list[str],
    ports: list[int],
    *,
    nmap_args: str | None,
    detect_os: bool,
    scripts: bool,
    timeout: float,
) -> dict[str, Any]:
    nmap_timeout = max(timeout * 60, 300.0)
    nmap_result = run_nmap(
        target_spec,
        ports,
        extra_args=nmap_args,
        detect_os=detect_os,
        scripts=scripts,
        timeout=nmap_timeout,
    )
    nmap_result["hostsScanned"] = len(ips)
    nmap_result["discoverOnly"] = not ports
    return nmap_result
