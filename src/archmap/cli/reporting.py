from __future__ import annotations

import argparse
import json

from archmap.exporters import (
    export_graph_as_cytoscape,
    export_graph_as_json,
    export_graph_as_mermaid,
)


def export_outputs(
    *,
    report: dict,
    output_format: str,
    json_output: str,
    mermaid_output: str,
    cytoscape_output: str,
    include_cytoscape: bool,
) -> dict:
    result = {"jsonPath": None, "mermaidPath": None, "cytoscapePath": None}

    if output_format in {"json", "both"}:
        result["jsonPath"] = str(export_graph_as_json(report, json_output))
    if output_format in {"mermaid", "both"}:
        result["mermaidPath"] = str(export_graph_as_mermaid(report, mermaid_output))
    if include_cytoscape:
        result["cytoscapePath"] = str(export_graph_as_cytoscape(report, cytoscape_output))

    return result


def print_summary(report: dict) -> None:
    metrics = report["metrics"]
    print(f"[ok] {metrics['filesAnalyzed']} files analyzed")
    print(f"[ok] {metrics['totalDependencies']} dependencies detected")
    print(f"[ok] {metrics['circularDependencyCount']} circular dependencies detected")
    coupling = metrics.get("coupling", {})
    if coupling:
        print(
            "[ok] Average instability "
            f"{round(float(coupling.get('averageInstability', 0.0)) * 100)}%"
        )
    architecture = report.get("architecture", {})
    health = architecture.get("health", {})
    style = architecture.get("detectedStyle", {})
    rule_violations = architecture.get("ruleViolations", [])
    active_rules = architecture.get("activeRules", {})
    if health:
        print(f"[ok] Architecture health {health.get('score', 0)}/100 ({health.get('grade', '?')})")
    if style:
        confidence = round(float(style.get("confidence", 0.0)) * 100)
        print(f"[ok] Detected style: {style.get('name', 'unknown')} ({confidence}% confidence)")
    configured_rules = len(active_rules.get("forbid", [])) + len(active_rules.get("allow", []))
    if configured_rules:
        print(f"[ok] {configured_rules} custom architecture rules configured")
    if rule_violations:
        print(f"[warn] {len(rule_violations)} custom architecture rule violations detected")


def print_top_complexity(report: dict, limit: int) -> None:
    if limit <= 0:
        return

    top_complexity = report["metrics"]["complexity"][:limit]
    if not top_complexity:
        return

    print("Top complexity (imports/dependents):")
    for item in top_complexity:
        score = round(float(item["score"]) * 100)
        instability = round(float(item.get("instability", 0.0)) * 100)
        dependents = int(item.get("dependents", 0))
        total_connections = int(item.get("totalConnections", item["imports"] + dependents))
        print(
            f"  - {item['file']}: {item['imports']} imports, "
            f"{dependents} dependents, {total_connections} total, "
            f"{instability}% instability ({score}% score)"
        )


def print_top_risks(report: dict, limit: int) -> None:
    if limit <= 0:
        return

    top_risks = report.get("risks", {}).get("top_risk_files", [])[:limit]
    if not top_risks:
        return

    print("Top risk files:")
    for item in top_risks:
        signals = ", ".join(item.get("signals", [])) or "none"
        print(f"  - {item['file']}: score {item['riskScore']} ({signals})")


def print_export_summary(export_result: dict) -> None:
    if export_result["jsonPath"]:
        print(f"[info] JSON report exported to {export_result['jsonPath']}")
    if export_result["mermaidPath"]:
        print(f"[info] Mermaid graph exported to {export_result['mermaidPath']}")
    if export_result["cytoscapePath"]:
        print(f"[info] Cytoscape data exported to {export_result['cytoscapePath']}")


def evaluate_quality_gates(report: dict, args: argparse.Namespace) -> list[str]:
    metrics = report.get("metrics", {})
    risks = report.get("risks", {})
    architecture = report.get("architecture", {})

    cycle_count = int(metrics.get("circularDependencyCount", 0))
    layer_count = len(risks.get("layer_violations", []))
    god_count = len(risks.get("god_modules", []))
    explosion_count = len(risks.get("dependency_explosions", []))
    custom_rule_count = len(architecture.get("ruleViolations", []))
    health_score = int(architecture.get("health", {}).get("score", 100))

    failures: list[str] = []
    if args.fail_on_cycles and cycle_count > 0:
        failures.append(f"cycle gate failed: {cycle_count} circular dependencies found")
    if args.fail_on_layer_violations and layer_count > 0:
        failures.append(f"layer gate failed: {layer_count} layer violations found")
    if args.fail_on_god_modules and god_count > 0:
        failures.append(f"god-module gate failed: {god_count} god modules found")
    if args.fail_on_dependency_explosions and explosion_count > 0:
        failures.append(
            f"dependency-explosion gate failed: {explosion_count} dependency explosions found"
        )
    if getattr(args, "fail_on_custom_rules", False) and custom_rule_count > 0:
        failures.append(
            "custom-rule gate failed: "
            f"{custom_rule_count} custom architecture rule violations found"
        )
    if args.fail_on_risks and (
        cycle_count > 0
        or layer_count > 0
        or god_count > 0
        or explosion_count > 0
        or custom_rule_count > 0
    ):
        failures.append(
            "risk gate failed: detected cycles/layer violations/god modules/"
            "dependency explosions/custom rule violations"
        )
    if getattr(args, "min_health", None) is not None and health_score < int(args.min_health):
        failures.append(
            "health gate failed: "
            f"architecture health {health_score} is below {int(args.min_health)}"
        )

    return failures


def format_diff_output(base_ref: str, head_ref: str, diff_result: dict) -> str:
    edge_delta = diff_result["edges"]["delta"]
    cycle_delta = diff_result["cycles"]["delta"]
    complexity_delta_percent = diff_result["complexity"]["deltaPercent"]
    risk_summary = diff_result["riskSummary"]
    architecture_summary = diff_result.get("architecture", {})

    lines = [
        f"Comparing {base_ref} -> {head_ref}",
        f"{signed(edge_delta)} dependencies",
        f"{signed(cycle_delta)} circular dependencies",
        f"complexity {signed_float(complexity_delta_percent)}%",
        f"health {signed(int(architecture_summary.get('healthDelta', 0)))}",
        f"{signed(risk_summary['layerViolationsDelta'])} layer violations",
        f"{signed(risk_summary['godModulesDelta'])} god modules",
        f"{signed(risk_summary['dependencyExplosionsDelta'])} dependency explosions",
        f"{signed(int(architecture_summary.get('ruleViolationsDelta', 0)))} custom rule violations",
    ]
    if architecture_summary.get("styleChanged"):
        lines.append(
            "style "
            f"{architecture_summary.get('baseStyle', 'unknown')} -> "
            f"{architecture_summary.get('headStyle', 'unknown')}"
        )

    file_summary = diff_result.get("files", {})
    file_delta = int(file_summary.get("delta", 0))
    added_files = file_summary.get("added", [])
    removed_files = file_summary.get("removed", [])
    changed_files = file_summary.get("changed", [])

    if file_delta or added_files or removed_files or changed_files:
        lines.append(f"{signed(file_delta)} files")

    if changed_files:
        lines.append("Top file deltas:")
        for item in changed_files[:5]:
            lines.append(
                "  - "
                f"{item['file']}: "
                f"out {signed(int(item['outgoingDelta']))}, "
                f"in {signed(int(item['incomingDelta']))}, "
                f"complexity {signed_float(float(item['complexityDelta']) * 100)}%, "
                f"risk {signed(int(item['riskScoreDelta']))}"
            )
    return "\n".join(lines)


def print_diff_output(
    base_ref: str,
    head_ref: str,
    diff_result: dict,
    as_json: bool = False,
) -> None:
    if as_json:
        print(json.dumps(diff_result, indent=2))
        return

    print(format_diff_output(base_ref, head_ref, diff_result))


def print_history_output(history: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(history, indent=2))
        return

    snapshots = history.get("snapshots", [])
    trend = history.get("trend", {})
    cycles = history.get("cycles", [])
    hotspots = history.get("hotspots", [])

    print(
        "History window: "
        f"{history.get('windowSize', 0)} snapshot(s) "
        f"from {history.get('ref', 'HEAD')}"
    )
    if snapshots:
        first = snapshots[0]
        last = snapshots[-1]
        print(
            f"Health {first['health']} -> {last['health']} "
            f"({signed(int(trend.get('healthDelta', 0)))})"
        )
        print(
            f"Cycles {first['cycles']} -> {last['cycles']} "
            f"({signed(int(trend.get('cycleDelta', 0)))})"
        )
        print(
            f"Dependencies {first['dependencies']} -> {last['dependencies']} "
            f"({signed(int(trend.get('dependencyDelta', 0)))})"
        )
        print(
            "Instability "
            f"{signed_float(float(trend.get('instabilityDeltaPercent', 0.0)))}%"
        )
        if trend.get("styleChanged"):
            print(
                "Style "
                f"{trend.get('fromStyle', 'unknown')} -> {trend.get('toStyle', 'unknown')}"
            )

    if cycles:
        print("Current cycle origins:")
        for item in cycles[:5]:
            introduced = item.get("introducedIn", {})
            owner = item.get("suspectedOwner", {})
            print(
                "  - "
                f"{' -> '.join(item.get('cycle', []))}: "
                f"introduced in {introduced.get('shortCommit', '?')} "
                f"({introduced.get('subject', 'unknown')})"
            )
            if owner:
                print(
                    "    "
                    f"last touched by {owner.get('author', 'unknown')} on "
                    f"{owner.get('file', 'unknown')} "
                    f"[{owner.get('shortCommit', '?')}]"
                )

    if hotspots:
        print("Architectural hotspots:")
        for hotspot in hotspots[:5]:
            touched = hotspot.get("lastTouched", {}) or {}
            signals = ", ".join(hotspot.get("signals", [])) or "none"
            print(
                "  - "
                f"{hotspot.get('file')}: score {hotspot.get('riskScore', 0)} "
                f"({signals})"
            )
            if touched:
                print(
                    "    "
                    f"last touched by {touched.get('author', 'unknown')} "
                    f"[{touched.get('shortCommit', '?')}]"
                )


def signed(value: int) -> str:
    return f"{value:+d}"


def signed_float(value: float) -> str:
    return f"{value:+.2f}"
