from __future__ import annotations

from archmap.core.analyzer.architecture_analyzer import analyze_architecture
from archmap.core.analyzer.complexity_analyzer import (
    annotate_nodes_with_complexity,
    summarize_complexity,
    summarize_coupling,
    summarize_critical_files,
)
from archmap.core.analyzer.cycle_detector import enrich_cycles, find_circular_dependencies
from archmap.core.analyzer.human_analyzer import analyze_human
from archmap.core.analyzer.impact_analyzer import calculate_impact
from archmap.core.analyzer.project_explainer import explain_project
from archmap.core.analyzer.risk_analyzer import detect_architectural_risks


def analyze_graph(
    graph: dict,
    layer_order: dict[str, int] | None = None,
    forbidden_rules: list[str] | None = None,
    allowed_rules: list[str] | None = None,
) -> dict:
    file_nodes = [node for node in graph["nodes"] if node.get("type") == "file"]
    file_node_ids = [node["id"] for node in file_nodes]
    file_node_set = set(file_node_ids)
    adjacency = _build_file_adjacency(file_node_ids, graph["edges"], file_node_set)

    cycles = find_circular_dependencies(file_node_ids, adjacency)
    cycle_membership = _build_cycle_membership(cycles)
    nodes = annotate_nodes_with_complexity(graph["nodes"], cycle_membership)
    edges = _annotate_edges(graph["edges"], cycle_membership)

    for node in nodes:
        node["impact"] = calculate_impact(node["id"], edges)

    incoming_counts = {node["id"]: int(node.get("incoming", 0)) for node in nodes}
    enriched = enrich_cycles(cycles, adjacency, incoming_counts)

    import_stats = graph.get("importStats", {})
    _total_i = int(import_stats.get("total", 0))
    _resolved_i = int(import_stats.get("resolved", 0))
    resolution_rate = round(min(_resolved_i / _total_i, 1.0), 3) if _total_i > 0 else 1.0
    # Cap unresolved list at 200 entries to keep the report payload manageable.
    _unresolved_raw: list[dict] = import_stats.get("unresolved", [])
    unresolved_imports = _unresolved_raw[:200]

    metrics = {
        "filesAnalyzed": len(file_nodes),
        "totalDependencies": len(graph["edges"]),
        "externalDependencies": len([node for node in nodes if node.get("type") == "package"]),
        "circularDependencyCount": len(cycles),
        "resolutionRate": resolution_rate,
        "unresolvedImports": unresolved_imports,
        "unresolvedImportsTotal": len(_unresolved_raw),
        "complexity": summarize_complexity(nodes),
        "coupling": summarize_coupling(nodes),
        "criticalFiles": summarize_critical_files(nodes),
    }

    risks = detect_architectural_risks(nodes, edges, cycles, layer_order=layer_order)
    architecture = analyze_architecture(
        nodes,
        edges,
        cycles,
        risks,
        layer_order=layer_order,
        forbidden_rules=forbidden_rules,
        allowed_rules=allowed_rules,
    )
    metrics["architectureHealthScore"] = architecture["health"]["score"]
    metrics["architectureStyle"] = architecture["detectedStyle"]["name"]
    metrics["architectureRuleViolations"] = len(architecture["ruleViolations"])

    return {
        "projectRoot": graph["projectRoot"],
        "nodes": nodes,
        "edges": edges,
        "metrics": metrics,
        "cycles": cycles,
        "cycleDetails": enriched,
        "risks": risks,
        "architecture": architecture,
        "insights": analyze_human({
            "metrics": metrics,
            "architecture": architecture,
            "cycles": cycles,
            "risks": risks,
        }),
        "explanation": explain_project(nodes, edges),
    }


def _build_file_adjacency(
    file_node_ids: list[str], edges: list[dict], file_node_set: set[str]
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in file_node_ids}

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source not in file_node_set or target not in file_node_set:
            continue
        adjacency[source].append(target)

    return adjacency


def _build_cycle_membership(cycles: list[list[str]]) -> dict[str, int]:
    membership: dict[str, int] = {}
    for index, cycle in enumerate(cycles):
        for node_id in cycle:
            membership[node_id] = index
    return membership


def _annotate_edges(edges: list[dict], cycle_membership: dict[str, int]) -> list[dict]:
    annotated = []
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        is_circular = (
            source in cycle_membership
            and target in cycle_membership
            and cycle_membership[source] == cycle_membership[target]
        )
        annotated.append(
            {
                **edge,
                "isCircular": is_circular,
            }
        )
    return annotated
