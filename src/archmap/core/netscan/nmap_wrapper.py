from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Any


def is_nmap_available() -> bool:
    return shutil.which("nmap") is not None


def _ports_arg(ports: list[int]) -> str:
    return ",".join(str(p) for p in ports)


def run_nmap(
    target: str,
    ports: list[int],
    *,
    extra_args: str | None = None,
    detect_os: bool = False,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Shell out to the system `nmap` binary and parse its XML output.

    Raises RuntimeError if nmap isn't installed, FileNotFoundError-style,
    or subprocess.TimeoutExpired if the scan runs longer than `timeout`.
    """
    if not is_nmap_available():
        raise RuntimeError(
            "nmap binary not found on PATH. Install it first "
            "(e.g. `pkg install nmap` on Termux, `apt install nmap` on Debian/Ubuntu)."
        )

    if ports:
        command = ["nmap", "-oX", "-", "-p", _ports_arg(ports), target]
    else:
        # No ports requested: a host-discovery-only ping scan.
        command = ["nmap", "-oX", "-", "-sn", target]
    if detect_os:
        # -O (OS fingerprinting) needs raw sockets, i.e. root.
        command.insert(-1, "-O")
    if extra_args:
        command.extend(extra_args.split())

    completed = subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"nmap exited with code {completed.returncode}: {stderr}")

    return _parse_nmap_xml(completed.stdout.decode("utf-8", errors="replace"))


def _parse_service_info(service_el: ET.Element | None) -> tuple[str, str | None]:
    if service_el is None:
        return "unknown", None
    service = service_el.get("name") or "unknown"
    parts = [service_el.get("product"), service_el.get("version"), service_el.get("extrainfo")]
    banner = " ".join(p for p in parts if p) or None
    return service, banner


def _parse_os_guess(host_el: ET.Element) -> str | None:
    best_match: ET.Element | None = None
    best_accuracy = -1
    for match_el in host_el.findall("os/osmatch"):
        accuracy = int(match_el.get("accuracy", 0))
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_match = match_el
    if best_match is None:
        return None
    name = best_match.get("name")
    return f"{name} ({best_accuracy}%)" if name else None


def _parse_runstats(root: ET.Element) -> dict[str, Any] | None:
    finished_el = root.find("runstats/finished")
    hosts_el = root.find("runstats/hosts")
    if finished_el is None and hosts_el is None:
        return None

    elapsed = finished_el.get("elapsed") if finished_el is not None else None
    hosts_up = hosts_el.get("up") if hosts_el is not None else None
    hosts_down = hosts_el.get("down") if hosts_el is not None else None

    return {
        "elapsedSeconds": float(elapsed) if elapsed else None,
        "hostsUp": int(hosts_up) if hosts_up else None,
        "hostsDown": int(hosts_down) if hosts_down else None,
    }


def _parse_nmap_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    hosts: list[dict[str, Any]] = []

    for host_el in root.findall("host"):
        status_el = host_el.find("status")
        state = status_el.get("state") if status_el is not None else "unknown"

        address_el = host_el.find("address")
        ip = address_el.get("addr") if address_el is not None else "unknown"

        hostname = None
        hostnames_el = host_el.find("hostnames/hostname")
        if hostnames_el is not None:
            hostname = hostnames_el.get("name")

        open_ports: list[dict[str, Any]] = []
        for port_el in host_el.findall("ports/port"):
            port_state_el = port_el.find("state")
            port_state = port_state_el.get("state") if port_state_el is not None else "unknown"
            if port_state != "open":
                continue

            service, banner = _parse_service_info(port_el.find("service"))
            open_ports.append(
                {
                    "port": int(port_el.get("portid")),
                    "protocol": port_el.get("protocol", "tcp"),
                    "state": "open",
                    "service": service,
                    "banner": banner,
                }
            )

        hosts.append(
            {
                "ip": ip,
                "hostname": hostname,
                "status": "up" if state == "up" else "down",
                "os": _parse_os_guess(host_el),
                "openPorts": open_ports,
            }
        )

    result: dict[str, Any] = {
        "engine": "nmap",
        "nmapVersion": root.get("version"),
        "hosts": hosts,
    }
    stats = _parse_runstats(root)
    if stats is not None:
        result["stats"] = stats
    return result
