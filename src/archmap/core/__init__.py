from __future__ import annotations

from pathlib import Path

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project


def analyze_project(project_path: str | Path) -> dict:
    parsed_project = parse_project(project_path)
    graph = build_graph(parsed_project)
    report = analyze_graph(graph)

    report["simple"] = {
        "nodes": [node["id"] for node in report["nodes"]],
        "edges": [[edge["source"], edge["target"]] for edge in report["edges"]],
    }
    return report
