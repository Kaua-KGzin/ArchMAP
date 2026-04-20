from __future__ import annotations

import argparse
import json

from archmap.exporters import (
    export_graph_as_cytoscape,
    export_graph_as_json,
    export_graph_as_mermaid,
    export_graph_as_sarif,
)


def export_outputs(
    *,
    report: dict,
    output_format: str,
    json_output: str,
    mermaid_output: str,
    cytoscape_output: str,
    sarif_output: str | None = None,
    include_cytoscape: bool,
    no_subgraphs: bool = False,
) -> dict:
    result = {"jsonPath": None, "mermaidPath": None, "cytoscapePath": None, "sarifPath": None}

    if output_format in {"json", "both"}:
        result["jsonPath"] = str(export_graph_as_json(report, json_output))
    if output_format in {"mermaid", "both"}:
        if no_subgraphs:
            mermaid_path = export_graph_as_mermaid(
                report,
                mermaid_output,
                no_subgraphs=True,
            )
        else:
            mermaid_path = export_graph_as_mermaid(report, mermaid_output)
        result["mermaidPath"] = str(mermaid_path)
    if include_cytoscape:
        result["cytoscapePath"] = str(export_graph_as_cytoscape(report, cytoscape_output))
    if sarif_output:
        result["sarifPath"] = str(export_graph_as_sarif(report, sarif_output))

    return result


def print_human_insights(report: dict) -> None:
    insights = report.get("insights")
    if not insights:
        return

    status = str(insights.get("status", "ok")).upper()
    print("\n[insight] Architectural reading")
    print(f"Status: {status}")
    print(f"Summary: {insights.get('message', 'No summary available.')}")

    problems = insights.get("problems") or []
    if problems:
        print("Problems:")
        for problem in problems:
            print(f"  - {problem}")

    actions = insights.get("actions") or []
    if actions:
        print("Next steps:")
        for action in actions:
            print(f"  - {action}")


def print_project_explanation(report: dict) -> None:
    explanation = report.get("explanation")
    if not explanation:
        return

    print("\n[explain] Project summary")
    print(f"Style: {explanation.get('architecture', 'Custom')}")
    simple_text = str(explanation.get("simple", "")).strip()
    technical_text = str(explanation.get("technical", "")).strip()
    if simple_text:
        print(simple_text)
    if technical_text:
        print("Technical view:")
        print(technical_text)


def print_impact_analysis(report: dict, target_path: str, max_impacted: int = 15) -> None:
    from archmap.utils.file_utils import normalize_file_id

    target_id = normalize_file_id(target_path)
    nodes = report.get("nodes", [])
    target_node = next((node for node in nodes if node["id"] == target_id), None)

    if not target_node:
        print(f"[error] File not found in graph: {target_path}")
        return

    impact = target_node.get("impact", {})
    impacted_files = impact.get("impactedFiles", [])
    count = int(impact.get("impactCount", 0))
    risk = str(impact.get("risk", "low")).upper()

    print(f"\n[risk] Impact analysis for {target_id}")
    print(f"Change risk: {risk}")
    print(f"Potentially impacted files: {count}")
    if count <= 0:
        print("  - No downstream files were detected.")
        return

    for file_path in impacted_files[:max(0, max_impacted)]:
        print(f"  - {file_path}")
    if count > max_impacted:
        print(f"  - ... and {count - max_impacted} more files")


def print_risk_report(risk_payload: dict, max_impacted: int = 15) -> None:
    file_id = risk_payload.get("file", "")
    impact = risk_payload.get("impact", {})
    score = int(risk_payload.get("riskScore", 0))
    signals = risk_payload.get("signals", []) or []
    incoming = int(risk_payload.get("incoming", 0))
    outgoing = int(risk_payload.get("outgoing", 0))

    print(f"[risk] {file_id}")
    print(f"Risk score: {score}")
    print(f"Signals: {', '.join(signals) if signals else 'none'}")
    print(f"Incoming dependencies: {incoming}")
    print(f"Outgoing dependencies: {outgoing}")
    print(f"Blast radius: {impact.get('impactCount', 0)} file(s)")
    for file_path in impact.get("impactedFiles", [])[:max(0, max_impacted)]:
        print(f"  - {file_path}")


def print_simple_map(simple_map: dict[str, list[str]]) -> None:
    if not simple_map:
        print("[map] No cross-group dependencies detected.")
        return

    print("[map] Simple architecture view")
    for source, targets in simple_map.items():
        if not targets:
            print(f"{source}")
            continue
        print(f"{source} -> {', '.join(targets)}")


def print_improve_report(suggestions: dict) -> None:
    print("[improve] Automatic architecture suggestions")
    print(suggestions.get("summary", "No suggestions generated."))

    groups = suggestions.get("groups", [])
    if groups:
        print("Suggested groups:")
        for group in groups:
            print(f"  - /{group['name']} ({group['count']} file(s))")

    moves = suggestions.get("moves", [])
    if moves:
        print("Suggested file moves:")
        for move in moves[:12]:
            print(f"  - {move['source']} -> {move['target']}")
        if len(moves) > 12:
            print(f"  - ... and {len(moves) - 12} more moves")


def print_summary(report: dict) -> None:
    metrics = report["metrics"]
    print(f"[ok] {metrics['filesAnalyzed']} files analyzed")
    print(f"[ok] {metrics['totalDependencies']} dependencies detected")

    cycle_count = int(metrics.get("circularDependencyCount", 0))
    print(f"[ok] {cycle_count} circular dependencies detected")
    if 0 < cycle_count <= 5:
        for detail in report.get("cycleDetails", [])[:cycle_count]:
            path = detail.get("path") or detail.get("members", [])
            members = path[:-1] if (path and path[0] == path[-1]) else path
            label = " → ".join(members[:5])
            if len(members) > 5:
                label += f" (+{len(members) - 5} more)"
            print(f"  ↻ {label}")
            suggestion = detail.get("breakSuggestion")
            if suggestion:
                print(f"    break: remove {suggestion['from']} → {suggestion['to']}")

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
        print(
            f"[ok] Architecture health {health.get('score', 0)}/100 "
            f"({health.get('grade', '?')})"
        )
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
    if export_result.get("sarifPath"):
        print(f"[info] SARIF report exported to {export_result['sarifPath']}")


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
