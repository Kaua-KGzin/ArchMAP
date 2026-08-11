from __future__ import annotations

import time
from typing import Any

from archmap.core.netscan.hosts import discover_hosts, parse_targets, reverse_lookup
from archmap.core.netscan.nmap_wrapper import run_nmap
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
    use_nmap: bool = False,
    nmap_args: str | None = None,
    timeout: float = 1.0,
    concurrency: int = 200,
) -> dict[str, Any]:
    """Discover live hosts on `target_spec` and, unless --discover-only, scan
    their open ports. Pure Python (stdlib-only) by default, or delegates to
    the system `nmap` binary when `use_nmap` is set.
    """
    started_at = time.time()
    ips = parse_targets(target_spec)
    ports = [] if discover_only else parse_ports(ports_spec, top=top_ports)

    if use_nmap:
        result = _run_with_nmap(target_spec, ips, ports, nmap_args=nmap_args, timeout=timeout)
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
    timeout: float,
) -> dict[str, Any]:
    nmap_timeout = max(timeout * 60, 300.0)
    nmap_result = run_nmap(target_spec, ports, extra_args=nmap_args, timeout=nmap_timeout)
    nmap_result["hostsScanned"] = len(ips)
    nmap_result["discoverOnly"] = not ports
    return nmap_result
