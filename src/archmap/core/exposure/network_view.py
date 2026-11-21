"""What the web UI's Network view shows: the stored snapshots, read-only.

`archmap serve` never scans the network itself. A scan from an HTTP handler
would be slow, would block the UI and would turn the server into a port
scanner for anyone who can reach it. The view reads what `archmap expose
--snapshot` or `archmap netscan --snapshot` already stored under
`.archmap/network/`, and diffs the latest snapshot against the previous one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from archmap.core.exposure.network_diff import (
    Observation,
    diff_network_snapshots,
    normalize_hosts,
    normalize_observations,
)
from archmap.core.exposure.snapshots import list_snapshots, load_snapshot

DEFAULT_MAX_PORTS = 500

_URGENT = {"high", "critical"}
_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

NO_SNAPSHOT_HINT = (
    "No network snapshot yet. Run `archmap expose <target> . --snapshot` "
    "(or `archmap netscan <target> --snapshot`) in this project, then refresh."
)


def _is_notable(observation: Observation) -> bool:
    """The `archmap memory` rule: worth acting on, not just open."""
    return bool(
        observation["drift"]
        or observation["riskLevel"] in _URGENT
        or observation["severity"] in _URGENT
    )


def _urgency(port: dict[str, Any]) -> tuple[int, int, int, str, int]:
    level = min(
        _RANK.get(str(port.get("severity") or ""), 5),
        _RANK.get(str(port.get("riskLevel") or ""), 5),
    )
    return (
        0 if port["drift"] else 1,
        0 if port["notable"] else 1,
        level,
        port["host"],
        port["port"],
    )


def _finding_ids(report: dict[str, Any]) -> dict[tuple[str, int, str], str]:
    ids: dict[tuple[str, int, str], str] = {}
    for finding in report.get("findings", []) or []:
        finding_id = finding.get("id")
        port = finding.get("port")
        if finding_id and isinstance(port, int):
            key = (str(finding.get("host") or ""), port, str(finding.get("protocol") or "tcp"))
            ids[key] = str(finding_id)
    return ids


def build_network_view(
    project_root: str | Path, *, max_ports: int = DEFAULT_MAX_PORTS
) -> dict[str, Any]:
    """Summarize the newest network snapshot of `project_root` for the browser.

    Never raises for missing or unreadable data: the view degrades to an
    `available: false` payload with a hint or an error message.
    """
    refs = list_snapshots(project_root)
    snapshots = [
        {"kind": ref["kind"], "target": ref["target"], "capturedAt": ref["capturedAt"]}
        for ref in refs
    ]
    if not refs:
        return {"available": False, "hint": NO_SNAPSHOT_HINT, "snapshots": []}

    try:
        latest = load_snapshot(refs[0]["path"])
        previous = load_snapshot(refs[1]["path"]) if len(refs) > 1 else None
    except (OSError, ValueError) as exc:
        return {"available": False, "error": str(exc), "snapshots": snapshots}

    report = latest["report"]
    diff = diff_network_snapshots(previous, latest) if previous is not None else None
    opened = {
        (o["host"], o["port"], o["protocol"]) for o in (diff or {}).get("portsOpened", [])
    }
    ids = _finding_ids(report)

    ports: list[dict[str, Any]] = []
    for observation in normalize_observations(report):
        key = (observation["host"], observation["port"], observation["protocol"])
        ports.append(
            {
                **observation,
                "id": ids.get(key),
                "notable": _is_notable(observation),
                "isNew": key in opened,
            }
        )
    ports.sort(key=_urgency)

    drift_violations = list(report.get("driftViolations", []) or [])
    summary = {
        "hosts": len(normalize_hosts(report)),
        "openPorts": len(ports),
        "notable": sum(1 for port in ports if port["notable"]),
        "driftViolations": len(drift_violations),
        "portsOpened": len(opened),
        "portsClosed": len((diff or {}).get("portsClosed", [])),
    }

    return {
        "available": True,
        "latest": {
            "kind": latest["kind"],
            "target": latest["target"],
            "capturedAt": latest["capturedAt"],
        },
        "snapshots": snapshots,
        "summary": summary,
        "ports": ports[:max_ports],
        "truncated": len(ports) > max_ports,
        "closedPorts": (diff or {}).get("portsClosed", [])[:max_ports],
        "driftViolations": drift_violations,
        "diff": None if diff is None else {"from": diff["from"], "summary": diff["summary"]},
    }
