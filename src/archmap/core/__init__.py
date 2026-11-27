from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archmap.cache import compute_fingerprint, load_cached_report, save_cached_report
from archmap.config import load_project_config
from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project
from archmap.core.perf.budget import Budget, BudgetSource
from archmap.core.perf.progress import Progress

__all__ = ["analyze_project"]


def analyze_project(
    project_path: str | Path,
    parallel: bool | None = None,
    use_cache: bool = True,
    time_budget: float | None = None,
    budget_source: BudgetSource = "cli",
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Analyze ``project_path``.

    ``time_budget`` is a soft limit in seconds for the whole run (``0`` = no
    limit; negative raises ``ValueError``). ``None`` falls back to
    ``[analysis.limits] time_budget_seconds``. ``budget_source`` names where an
    explicit ``time_budget`` came from (``"cli"``, ``"mcp-default"``, ``"mcp-arg"``);
    a budget taken from the config is always ``"config"``. A run the budget
    reduced is never written to the cache. ``progress`` (default ``None`` = no
    progress output) only reports; it never changes the report.
    """
    project_root = Path(project_path).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"project path does not exist: {project_root}")

    config = load_project_config(project_root)
    # The clock starts before discovery: the budget covers the whole run.
    budget = (
        Budget(time_budget, source=budget_source)
        if time_budget is not None
        else Budget(config["analysis"]["limits"]["time_budget_seconds"], source="config")
    )

    if use_cache:
        fingerprint = compute_fingerprint(project_root, config, budget.seconds)
        cached = load_cached_report(project_root, fingerprint)
        if cached is not None:
            return cached

    use_parallel = parallel if parallel is not None else config["analysis"]["parallel"]
    on_done: Callable[[], None] | None = None
    on_discovered: Callable[[int], None] | None = None
    if progress is not None:
        reporter = progress
        reporter.stage("discover")
        counter = {"done": 0, "total": 0}
        count_lock = threading.Lock()

        def _discovered(total: int) -> None:
            counter["total"] = total
            reporter.stage("parse")

        def _done() -> None:
            with count_lock:
                counter["done"] += 1
                done = counter["done"]
            reporter.advance(done, counter["total"])

        on_done, on_discovered = _done, _discovered

    parsed_project = parse_project(
        project_root,
        config=config,
        parallel=use_parallel,
        on_file_done=on_done,
        on_discovered=on_discovered,
    )
    if progress is not None:
        progress.stage("analyze")
    graph = build_graph(parsed_project)
    report = analyze_graph(
        graph,
        layer_order=config["risks"]["layer_order"],
        forbidden_rules=config["architecture"]["rules"]["forbid"],
        allowed_rules=config["architecture"]["rules"]["allow"],
        budget=budget,
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

    # Reduced data must never be served to a later run.
    if use_cache and not budget.reductions:
        save_cached_report(project_root, fingerprint, report)

    return report
