from __future__ import annotations

import subprocess
from pathlib import Path

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project
from archmap.utils.file_utils import file_language_from_id, normalize_file_id


def analyze_git_ref(project_root: str | Path, ref: str) -> dict:
    root = Path(project_root).resolve()
    virtual_files = _load_git_files(root, ref)

    parsed = parse_project(root, virtual_files=virtual_files)
    graph = build_graph(parsed)
    analyzed = analyze_graph(graph)
    analyzed["simple"] = {
        "nodes": [node["id"] for node in analyzed["nodes"]],
        "edges": [[edge["source"], edge["target"]] for edge in analyzed["edges"]],
    }
    return analyzed


def diff_reports(base_report: dict, head_report: dict) -> dict:
    base_edges = {tuple(edge) for edge in base_report.get("simple", {}).get("edges", [])}
    head_edges = {tuple(edge) for edge in head_report.get("simple", {}).get("edges", [])}
    added_edges = sorted(head_edges - base_edges)
    removed_edges = sorted(base_edges - head_edges)

    base_cycle_count = int(base_report["metrics"]["circularDependencyCount"])
    head_cycle_count = int(head_report["metrics"]["circularDependencyCount"])
    cycle_delta = head_cycle_count - base_cycle_count

    base_complexity = _average_complexity(base_report)
    head_complexity = _average_complexity(head_report)
    complexity_delta = head_complexity - base_complexity
    complexity_percent = 0.0
    if base_complexity > 0:
        complexity_percent = (complexity_delta / base_complexity) * 100
    elif head_complexity > 0:
        complexity_percent = 100.0

    base_risks = base_report.get("risks", {})
    head_risks = head_report.get("risks", {})

    return {
        "baseRef": base_report.get("ref"),
        "headRef": head_report.get("ref"),
        "edges": {
            "added": added_edges,
            "removed": removed_edges,
            "delta": len(added_edges) - len(removed_edges),
        },
        "cycles": {
            "base": base_cycle_count,
            "head": head_cycle_count,
            "delta": cycle_delta,
        },
        "complexity": {
            "baseAverageScore": round(base_complexity, 6),
            "headAverageScore": round(head_complexity, 6),
            "delta": round(complexity_delta, 6),
            "deltaPercent": round(complexity_percent, 2),
        },
        "riskSummary": {
            "baseTopRisks": len(base_risks.get("top_risk_files", [])),
            "headTopRisks": len(head_risks.get("top_risk_files", [])),
            "layerViolationsDelta": len(head_risks.get("layer_violations", []))
            - len(base_risks.get("layer_violations", [])),
            "godModulesDelta": len(head_risks.get("god_modules", []))
            - len(base_risks.get("god_modules", [])),
            "dependencyExplosionsDelta": len(head_risks.get("dependency_explosions", []))
            - len(base_risks.get("dependency_explosions", [])),
        },
    }


def _average_complexity(report: dict) -> float:
    complexity_entries = report["metrics"].get("complexity", [])
    if not complexity_entries:
        return 0.0
    total = sum(float(entry.get("score", 0.0)) for entry in complexity_entries)
    return total / len(complexity_entries)


def _load_git_files(project_root: Path, ref: str) -> dict[str, str]:
    ls_tree = _run_git(project_root, ["ls-tree", "-r", "--name-only", ref])
    file_ids = [normalize_file_id(line.strip()) for line in ls_tree.splitlines() if line.strip()]

    files: dict[str, str] = {}
    for file_id in file_ids:
        if file_language_from_id(file_id) is None:
            continue
        show_result = _run_git(project_root, ["show", f"{ref}:{file_id}"], allow_failure=True)
        if show_result is None:
            continue
        files[file_id] = show_result
    return files


def _run_git(project_root: Path, args: list[str], allow_failure: bool = False) -> str | None:
    process = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode == 0:
        return process.stdout
    if allow_failure:
        return None
    raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "git command failed")
