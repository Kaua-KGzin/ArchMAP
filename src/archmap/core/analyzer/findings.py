"""Build a unified findings list from code-side architectural risks and cycle details."""

from __future__ import annotations

from typing import Any

from archmap.types import Finding

SEVERITY_LEVELS = ("info", "low", "medium", "high", "critical")


def max_severity(a: str, b: str) -> str:
    """Return the higher (worse) of two severity levels."""
    a_idx = SEVERITY_LEVELS.index(a) if a in SEVERITY_LEVELS else -1
    b_idx = SEVERITY_LEVELS.index(b) if b in SEVERITY_LEVELS else -1
    return a if a_idx >= b_idx else b


def build_code_findings(
    cycle_details: list[dict[str, Any]],
    risks: dict[str, Any],
    architecture: dict[str, Any],
) -> list[Finding]:
    """Transform code-side architectural risks into unified Finding objects.

    Takes the existing `risks` dict (god_modules, layer_violations,
    dependency_explosions), `cycle_details` (enriched cycle metadata), and
    `architecture.ruleViolations` and reshapes them into a stable, ordered
    `Finding` list with deterministic IDs (`ARCH-001`, `ARCH-002`, ...).

    Never mutates input dicts; all findings get `domain: "code"`,
    `confidence: 1.0` (deterministic static graph analysis).
    """
    findings: list[Finding] = []
    finding_id = 1

    if not cycle_details:
        cycle_details = []
    if not risks:
        risks = {}
    if not architecture:
        architecture = {}

    for cycle in cycle_details:
        members = cycle.get("members", [])
        path = cycle.get("path", [])
        message = f"Circular dependency: {' → '.join(path[:3])}"
        if len(path) > 3:
            message += f" (… {len(path) - 3} more)"

        evidence = [f"Members: {', '.join(members)}"]
        break_suggestion = cycle.get("breakSuggestion")
        if break_suggestion:
            evidence.append(f"Suggestion: {break_suggestion.get('reason', '')}")

        findings.append(
            Finding(
                id=f"ARCH-{finding_id:03d}",
                domain="code",
                category="circular_dependency",
                severity="high",
                confidence=1.0,
                message=message,
                evidence=evidence,
            )
        )
        finding_id += 1

    for god_module in risks.get("god_modules", []):
        file_id = god_module.get("file", "")
        outgoing = int(god_module.get("outgoing", 0))
        findings.append(
            Finding(
                id=f"ARCH-{finding_id:03d}",
                domain="code",
                category="god_module",
                severity="medium",
                confidence=1.0,
                message=f"God module: {file_id} has {outgoing} outgoing dependencies",
                evidence=[f"File: {file_id}", f"Outgoing: {outgoing}"],
                file=file_id,
            )
        )
        finding_id += 1

    for layer_violation in risks.get("layer_violations", []):
        source = layer_violation.get("source", "")
        target = layer_violation.get("target", "")
        source_layer = layer_violation.get("sourceLayer", "")
        target_layer = layer_violation.get("targetLayer", "")
        rule = layer_violation.get("rule", "")

        findings.append(
            Finding(
                id=f"ARCH-{finding_id:03d}",
                domain="code",
                category="layer_violation",
                severity="medium",
                confidence=1.0,
                message=f"{source_layer} → {target_layer}: {rule}",
                evidence=[
                    f"Source: {source} ({source_layer})",
                    f"Target: {target} ({target_layer})",
                ],
                source=source,
                target=target,
            )
        )
        finding_id += 1

    for explosion in risks.get("dependency_explosions", []):
        file_id = explosion.get("file", "")
        total_connections = int(explosion.get("totalConnections", 0))
        incoming = int(explosion.get("incoming", 0))
        outgoing = int(explosion.get("outgoing", 0))

        findings.append(
            Finding(
                id=f"ARCH-{finding_id:03d}",
                domain="code",
                category="dependency_explosion",
                severity="low",
                confidence=1.0,
                message=f"Dependency explosion: {file_id} ({total_connections} total connections)",
                evidence=[
                    f"File: {file_id}",
                    f"Incoming: {incoming}, Outgoing: {outgoing}",
                ],
                file=file_id,
            )
        )
        finding_id += 1

    for rule_violation in architecture.get("ruleViolations", []):
        source = rule_violation.get("source", "")
        target = rule_violation.get("target", "")
        message = rule_violation.get("message", "Rule violation")

        findings.append(
            Finding(
                id=f"ARCH-{finding_id:03d}",
                domain="code",
                category="rule_violation",
                severity="high",
                confidence=1.0,
                message=message,
                evidence=[
                    f"Source: {source}",
                    f"Target: {target}",
                    f"Kind: {rule_violation.get('kind', 'unknown')}",
                ],
                source=source,
                target=target,
            )
        )
        finding_id += 1

    return findings
