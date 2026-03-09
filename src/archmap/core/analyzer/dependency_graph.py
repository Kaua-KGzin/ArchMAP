from __future__ import annotations

from archmap.core.analyzer.complexity_analyzer import (
    annotate_nodes_with_complexity,
    summarize_complexity,
    summarize_critical_files,
)
from archmap.core.analyzer.cycle_detector import find_circular_dependencies
from archmap.core.analyzer.risk_analyzer import detect_architectural_risks


def analyze_graph(graph: dict) -> dict:
    file_nodes = [node for node in graph["nodes"] if node.get("type") == "file"]
    file_node_ids = [node["id"] for node in file_nodes]
    file_node_set = set(file_node_ids)
    adjacency = _build_file_adjacency(file_node_ids, graph["edges"], file_node_set)

    cycles = find_circular_dependencies(file_node_ids, adjacency)
    cycle_membership = _build_cycle_membership(cycles)
    nodes = annotate_nodes_with_complexity(graph["nodes"], cycle_membership)
    edges = _annotate_edges(graph["edges"], cycle_membership)

    metrics = {
        "filesAnalyzed": len(file_nodes),
        "totalDependencies": len(graph["edges"]),
        "externalDependencies": len(
            [node for node in nodes if node.get("type") == "package"]
        ),
        "circularDependencyCount": len(cycles),
        "complexity": summarize_complexity(nodes),
        "criticalFiles": summarize_critical_files(nodes),
    }

    risks = detect_architectural_risks(nodes, edges, cycles)

    return {
        "projectRoot": graph["projectRoot"],
        "nodes": nodes,
        "edges": edges,
        "metrics": metrics,
        "cycles": cycles,
        "risks": risks,
    }


def _build_file_adjacency(
    file_node_ids: list[str], edges: list[dict], file_node_set: set[str]
) -> dict[str, list[str]]:
    adjacency = {node_id: [] for node_id in file_node_ids}

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
