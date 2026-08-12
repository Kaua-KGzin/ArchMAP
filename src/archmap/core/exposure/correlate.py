from __future__ import annotations

from typing import Any

from archmap.config import NetworkRulesConfig
from archmap.core.analyzer.rule_engine import detect_rule_violations, rule_tokens
from archmap.core.exposure.endpoint_scanner import EndpointReference
from archmap.core.exposure.service_packages import package_hints_for_service

_SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# Endpoint matches below this confidence are too weak to treat as a "this
# file connects here" signal for drift/rule checking — only exact host:port
# matches (with agreeing or unknown declared service) qualify.
_CONSUMER_EDGE_MIN_CONFIDENCE = 0.7

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
    network_risk: dict[str, Any] | None,
    matched_packages: list[dict[str, Any]],
    has_drift_violation: bool,
) -> str:
    severity = "info"
    if network_risk:
        network_severity = _NETWORK_RISK_TO_SEVERITY.get(network_risk["level"], "info")
        severity = _max_severity(severity, network_severity)
    for match in matched_packages:
        code_severity = _CODE_IMPACT_RISK_TO_SEVERITY.get(match["risk"], "info")
        severity = _max_severity(severity, code_severity)
    if has_drift_violation:
        severity = _max_severity(severity, "high")
    return severity


def _match_endpoint(
    host: str | None,
    hostname: str | None,
    port: int | None,
    endpoint_refs: list[EndpointReference],
) -> EndpointReference | None:
    for ref in endpoint_refs:
        if ref["port"] != port:
            continue
        if ref["host"] == host or (hostname is not None and ref["host"] == hostname):
            return ref
    return None


def _confidence_for_finding(
    service: str,
    endpoint_match: EndpointReference | None,
    matched_packages: list[dict[str, Any]],
) -> tuple[float, list[str]]:
    if endpoint_match is not None:
        reasons = [f"exact host:port match found in {endpoint_match['file']}"]
        declared_service = endpoint_match["service"]
        if declared_service and declared_service != service:
            reasons.append(
                f"config indicates '{declared_service}' but the scan detected '{service}'"
            )
            return 0.7, reasons
        return 0.95, reasons
    if matched_packages:
        return 0.4, [
            f"'{matched_packages[0]['package']}' is imported by the project, but no "
            "explicit host:port configuration was found matching the scanned target"
        ]
    return 0.0, []


def correlate_exposure(
    netscan_report: dict[str, Any],
    analysis_report: dict[str, Any],
    endpoint_refs: list[EndpointReference] | None = None,
    network_rules: NetworkRulesConfig | None = None,
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

    When `endpoint_refs` (from `endpoint_scanner.scan_endpoint_references`)
    is given, each finding also gets a `confidence` score: an exact
    host:port literal found in the codebase is much stronger evidence than
    a service-name-to-package-import guess. When `network_rules` (a
    `{"forbid": [...], "allow": [...]}` dict of `"source-tag -> service-tag"`
    rules, e.g. from `.archmap.toml`'s `[network.rules]`) is also given,
    high-confidence matches are checked against those declared rules —
    a violation ("frontend" connects straight to "postgresql" when only
    "backend -> postgresql" is allowed) is a drift finding, surfaced both
    per-finding and in the top-level `driftViolations` list.

    Neither input report is mutated; this returns a new, independent dict.
    """
    nodes = analysis_report.get("nodes", [])
    endpoint_refs = endpoint_refs or []
    findings: list[dict[str, Any]] = []
    consumer_edges: list[dict[str, Any]] = []

    for host in netscan_report.get("hosts", []):
        for port_info in host.get("openPorts", []):
            service = port_info.get("service", "unknown")
            network_risk = port_info.get("risk")
            port = port_info.get("port")
            matched_packages = _match_packages(service, nodes)
            endpoint_match = _match_endpoint(
                host.get("ip"), host.get("hostname"), port, endpoint_refs
            )
            confidence, confidence_reasons = _confidence_for_finding(
                service, endpoint_match, matched_packages
            )

            finding: dict[str, Any] = {
                "host": host.get("ip"),
                "hostname": host.get("hostname"),
                "port": port,
                "protocol": port_info.get("protocol", "tcp"),
                "service": service,
                "networkRisk": network_risk,
                "matchedPackages": matched_packages,
                "confidence": confidence,
                "confidenceReasons": confidence_reasons,
                "driftViolation": None,
            }
            findings.append(finding)

            if endpoint_match is not None and confidence >= _CONSUMER_EDGE_MIN_CONFIDENCE:
                consumer_edges.append(
                    {"source": endpoint_match["file"], "target": service, "finding": finding}
                )

    drift_violations: list[dict[str, Any]] = []
    if network_rules and consumer_edges:
        raw_violations = detect_rule_violations(
            [{"source": edge["source"], "target": edge["target"]} for edge in consumer_edges],
            network_rules.get("forbid", []),
            network_rules.get("allow", []),
            target_tags_fn=rule_tokens,
        )
        findings_by_edge: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for edge in consumer_edges:
            key = (edge["source"], edge["target"])
            findings_by_edge.setdefault(key, []).append(edge["finding"])

        for violation in raw_violations:
            drift_violations.append(violation)
            key = (violation["source"], violation["target"])
            for finding in findings_by_edge.get(key, []):
                finding["driftViolation"] = violation

    for finding in findings:
        has_drift = finding["driftViolation"] is not None
        finding["severity"] = _finding_severity(
            finding["networkRisk"], finding["matchedPackages"], has_drift
        )

    return {
        "target": netscan_report.get("target"),
        "projectRoot": analysis_report.get("projectRoot"),
        "findings": findings,
        "driftViolations": drift_violations,
        "summary": {
            "openPorts": len(findings),
            "matchedToCode": sum(1 for f in findings if f["matchedPackages"]),
            "highSeverity": sum(1 for f in findings if f["severity"] in ("high", "critical")),
            "driftViolations": len(drift_violations),
        },
    }
