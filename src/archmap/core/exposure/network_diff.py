"""Diff two network snapshots — the network-side counterpart to `archmap diff`.

`netscan` and `expose` produce differently-shaped reports (a host/port tree
vs. a flat correlated findings list), so both are first normalized into one
`Observation` per `host:port/protocol`. Everything downstream — opened and
closed ports, service and risk changes, drift violations that appeared or
were resolved — is computed on that common shape, which means a `netscan`
snapshot and an `expose` snapshot of the same target diff cleanly against
each other.
"""

from __future__ import annotations

from typing import Any, TypedDict

from archmap.core.exposure.snapshots import Snapshot

ObservationKey = tuple[str, int, str]


class Observation(TypedDict):
    """One open port seen on one host, from either report shape."""

    host: str
    hostname: str | None
    port: int
    protocol: str
    service: str
    riskLevel: str | None
    severity: str | None
    confidence: float | None
    drift: str | None


# Functional TypedDict form because "from" is a Python keyword and the JSON
# key readers expect is `from`/`to`, not `from_`.
FieldChange = TypedDict(
    "FieldChange",
    {
        "host": str,
        "hostname": str | None,
        "port": int,
        "protocol": str,
        "field": str,
        "from": str | None,
        "to": str | None,
    },
)
"""A single field that differs for a port present in both snapshots."""


class HostEntry(TypedDict):
    host: str
    hostname: str | None


def _observation(
    host: str,
    hostname: str | None,
    port: Any,
    protocol: Any,
    service: Any,
    risk: dict[str, Any] | None,
    *,
    severity: str | None = None,
    confidence: float | None = None,
    drift: str | None = None,
) -> Observation | None:
    if port is None:
        return None
    return {
        "host": host,
        "hostname": hostname or None,
        "port": int(port),
        "protocol": str(protocol or "tcp"),
        "service": str(service or "unknown"),
        "riskLevel": str(risk["level"]) if risk and risk.get("level") else None,
        "severity": severity,
        "confidence": confidence,
        "drift": drift,
    }


def normalize_observations(report: dict[str, Any]) -> list[Observation]:
    """Flatten a `netscan` or `expose` report into comparable observations.

    An `expose` report is detected by its `findings` key; anything else is
    read as a `netscan` host tree. Observations are returned sorted by
    host/port/protocol so callers get deterministic output.
    """
    observations: list[Observation] = []

    if "findings" in report:
        for finding in report.get("findings", []):
            drift = finding.get("driftViolation") or None
            observation = _observation(
                str(finding.get("host") or ""),
                finding.get("hostname"),
                finding.get("port"),
                finding.get("protocol"),
                finding.get("service"),
                finding.get("networkRisk"),
                severity=finding.get("severity"),
                confidence=finding.get("confidence"),
                drift=str(drift["message"]) if drift else None,
            )
            if observation is not None:
                observations.append(observation)
    else:
        for host in report.get("hosts", []):
            for port_info in host.get("openPorts", []):
                observation = _observation(
                    str(host.get("ip") or ""),
                    host.get("hostname"),
                    port_info.get("port"),
                    port_info.get("protocol"),
                    port_info.get("service"),
                    port_info.get("risk"),
                )
                if observation is not None:
                    observations.append(observation)

    observations.sort(key=lambda item: (item["host"], item["port"], item["protocol"]))
    return observations


def normalize_hosts(report: dict[str, Any]) -> list[HostEntry]:
    """Every host the report saw as up, including ones with no open ports.

    A `netscan` report lists live hosts explicitly; an `expose` report only
    mentions a host when it has at least one open port, so there its host
    list is derived from the findings.
    """
    seen: dict[str, HostEntry] = {}

    if "findings" in report:
        for finding in report.get("findings", []):
            host = str(finding.get("host") or "")
            if host and host not in seen:
                seen[host] = {"host": host, "hostname": finding.get("hostname") or None}
    else:
        for host_entry in report.get("hosts", []):
            host = str(host_entry.get("ip") or "")
            if host and host not in seen:
                seen[host] = {"host": host, "hostname": host_entry.get("hostname") or None}

    return [seen[host] for host in sorted(seen)]


def _key(observation: Observation) -> ObservationKey:
    return (observation["host"], observation["port"], observation["protocol"])


def _field_change(
    observation: Observation, field: str, before: str | None, after: str | None
) -> FieldChange:
    return {
        "host": observation["host"],
        "hostname": observation["hostname"],
        "port": observation["port"],
        "protocol": observation["protocol"],
        "field": field,
        "from": before,
        "to": after,
    }


def _drift_key(violation: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(violation.get("source", "")),
        str(violation.get("target", "")),
        str(violation.get("kind", "")),
        str(violation.get("rule", "")),
    )


def _diff_drift_violations(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before_map = {_drift_key(v): v for v in before.get("driftViolations", [])}
    after_map = {_drift_key(v): v for v in after.get("driftViolations", [])}
    new = [after_map[key] for key in after_map if key not in before_map]
    resolved = [before_map[key] for key in before_map if key not in after_map]
    return new, resolved


def _snapshot_meta(snapshot: Snapshot) -> dict[str, str]:
    return {
        "kind": snapshot["kind"],
        "target": snapshot["target"],
        "capturedAt": snapshot["capturedAt"],
    }


def diff_network_snapshots(before: Snapshot, after: Snapshot) -> dict[str, Any]:
    """Compare two snapshots and report what changed on the network.

    `before` is the older baseline and `after` the newer observation, so
    "opened" means a port present in `after` but not `before`. Neither
    snapshot is mutated. The two snapshots do not have to be of the same
    kind or even the same target — comparing across targets is unusual but
    the caller, not this function, decides whether that's meaningful.
    """
    before_report = before["report"]
    after_report = after["report"]

    before_observations = {_key(o): o for o in normalize_observations(before_report)}
    after_observations = {_key(o): o for o in normalize_observations(after_report)}

    ports_opened = [
        observation
        for key, observation in after_observations.items()
        if key not in before_observations
    ]
    ports_closed = [
        observation
        for key, observation in before_observations.items()
        if key not in after_observations
    ]

    service_changes: list[FieldChange] = []
    risk_changes: list[FieldChange] = []
    for key, current in after_observations.items():
        previous = before_observations.get(key)
        if previous is None:
            continue
        if previous["service"] != current["service"]:
            service_changes.append(
                _field_change(current, "service", previous["service"], current["service"])
            )
        if previous["riskLevel"] != current["riskLevel"]:
            risk_changes.append(
                _field_change(current, "riskLevel", previous["riskLevel"], current["riskLevel"])
            )

    before_hosts = {entry["host"]: entry for entry in normalize_hosts(before_report)}
    after_hosts = {entry["host"]: entry for entry in normalize_hosts(after_report)}
    hosts_appeared = [after_hosts[host] for host in sorted(after_hosts) if host not in before_hosts]
    hosts_disappeared = [
        before_hosts[host] for host in sorted(before_hosts) if host not in after_hosts
    ]

    drift_new, drift_resolved = _diff_drift_violations(before_report, after_report)

    counts = {
        "portsOpened": len(ports_opened),
        "portsClosed": len(ports_closed),
        "serviceChanges": len(service_changes),
        "riskChanges": len(risk_changes),
        "hostsAppeared": len(hosts_appeared),
        "hostsDisappeared": len(hosts_disappeared),
        "driftViolationsNew": len(drift_new),
        "driftViolationsResolved": len(drift_resolved),
    }
    summary: dict[str, Any] = {**counts, "changed": any(counts.values())}

    return {
        "from": _snapshot_meta(before),
        "to": _snapshot_meta(after),
        "hostsAppeared": hosts_appeared,
        "hostsDisappeared": hosts_disappeared,
        "portsOpened": sorted(ports_opened, key=_key),
        "portsClosed": sorted(ports_closed, key=_key),
        "serviceChanges": service_changes,
        "riskChanges": risk_changes,
        "driftViolationsNew": drift_new,
        "driftViolationsResolved": drift_resolved,
        "summary": summary,
    }
