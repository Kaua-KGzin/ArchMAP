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

            service_el = port_el.find("service")
            service = service_el.get("name") if service_el is not None else "unknown"
            product = service_el.get("product") if service_el is not None else None
            version = service_el.get("version") if service_el is not None else None
            banner = " ".join(p for p in (product, version) if p) or None

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
                "openPorts": open_ports,
            }
        )

    return {"engine": "nmap", "hosts": hosts}
