from __future__ import annotations

from pathlib import Path

from archmap.config import load_project_config
from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project


def analyze_project(project_path: str | Path) -> dict:
    project_root = Path(project_path).resolve()
    config = load_project_config(project_root)
    parsed_project = parse_project(project_root, config=config)
    graph = build_graph(parsed_project)
    report = analyze_graph(
        graph,
        layer_order=config["risks"]["layer_order"],
        forbidden_rules=config["architecture"]["rules"]["forbid"],
        allowed_rules=config["architecture"]["rules"]["allow"],
    )

    report["simple"] = {
        "nodes": [node["id"] for node in report["nodes"]],
        "edges": [[edge["source"], edge["target"]] for edge in report["edges"]],
    }
    return report
