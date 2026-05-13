from __future__ import annotations

from pathlib import Path
from typing import Any

from archmap.cache import compute_fingerprint, load_cached_report, save_cached_report
from archmap.config import load_project_config
from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project
from archmap.types import AnalysisResult

__all__ = ["analyze_project"]


def analyze_project(
    project_path: str | Path,
    parallel: bool | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    project_root = Path(project_path).resolve()
    config = load_project_config(project_root)

    if use_cache:
        fingerprint = compute_fingerprint(project_root, config)
        cached = load_cached_report(project_root, fingerprint)
        if cached is not None:
            return cached

    use_parallel = parallel if parallel is not None else config["analysis"]["parallel"]
    parsed_project = parse_project(project_root, config=config, parallel=use_parallel)
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

    # Embed budget config in report so CLI gate can access it without re-loading config.
    budgets = config["analysis"].get("budgets", {})
    if budgets:
        report["_configBudgets"] = {
            k: v for k, v in budgets.items() if v is not None
        }

    if use_cache:
        save_cached_report(project_root, fingerprint, report)

    return report
