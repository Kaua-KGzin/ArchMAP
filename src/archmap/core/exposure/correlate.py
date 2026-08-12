from __future__ import annotations

from typing import Any

from archmap.core.exposure.service_packages import package_hints_for_service

_SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

_NETWORK_RISK_TO_SEVERITY = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}

# archmap.core.analyzer.impact_analyzer.calculate_impact's risk tiers,
# mapped onto the same info..critical scale used here.
_CODE_IMPACT_RISK_TO_SEVERITY = {
    "low": "info",
    "ok": "low",
    "warning": "medium",
    "critical": "critical",
}


def _max_severity(a: str, b: str) -> str:
    return a if _SEVERITY_ORDER.index(a) >= _SEVERITY_ORDER.index(b) else b


def _match_packages(service: str, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hint_names = set(package_hints_for_service(service))
    if not hint_names:
        return []

    matches: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("type") != "package" or str(node.get("label", "")) not in hint_names:
            continue
        impact = node.get("impact") or {}
        matches.append(
            {
                "package": node.get("label"),
                "nodeId": node.get("id"),
                "impactCount": impact.get("impactCount", 0),
                "impactedFiles": impact.get("impactedFiles", []),
                "risk": impact.get("risk", "low"),
            }
        )
    return matches


def _finding_severity(
    network_risk: dict[str, Any] | None, matched_packages: list[dict[str, Any]]
) -> str:
    severity = "info"
    if network_risk:
        network_severity = _NETWORK_RISK_TO_SEVERITY.get(network_risk["level"], "info")
        severity = _max_severity(severity, network_severity)
    for match in matched_packages:
        code_severity = _CODE_IMPACT_RISK_TO_SEVERITY.get(match["risk"], "info")
        severity = _max_severity(severity, code_severity)
    return severity


def correlate_exposure(
    netscan_report: dict[str, Any], analysis_report: dict[str, Any]
) -> dict[str, Any]:
    """Cross-reference open network ports/services against the codebase's
    dependency graph.

    For each open port whose service has known client-package hints
    (`service_packages.SERVICE_PACKAGE_HINTS`), finds matching `pkg:<name>`
    nodes in the dependency graph and surfaces their already-computed blast
    radius (`archmap.core.analyzer.impact_analyzer`) alongside the port's
    own network-side risk rating. Every open port is included as a finding,
    even with no signal at all (`severity: "info"`), so consumers get the
    full picture rather than a silently filtered list.

    Neither input report is mutated; this returns a new, independent dict.
    """
    nodes = analysis_report.get("nodes", [])
    findings: list[dict[str, Any]] = []

    for host in netscan_report.get("hosts", []):
        for port_info in host.get("openPorts", []):
            service = port_info.get("service", "unknown")
            network_risk = port_info.get("risk")
            matched_packages = _match_packages(service, nodes)

            findings.append(
                {
                    "host": host.get("ip"),
                    "hostname": host.get("hostname"),
                    "port": port_info.get("port"),
                    "protocol": port_info.get("protocol", "tcp"),
                    "service": service,
                    "networkRisk": network_risk,
                    "matchedPackages": matched_packages,
                    "severity": _finding_severity(network_risk, matched_packages),
                }
            )

    return {
        "target": netscan_report.get("target"),
        "projectRoot": analysis_report.get("projectRoot"),
        "findings": findings,
        "summary": {
            "openPorts": len(findings),
            "matchedToCode": sum(1 for f in findings if f["matchedPackages"]),
            "highSeverity": sum(1 for f in findings if f["severity"] in ("high", "critical")),
        },
    }
