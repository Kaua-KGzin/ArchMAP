from __future__ import annotations

import json
import subprocess
from pathlib import Path

from archmap.config import CONFIG_FILENAMES, load_project_config
from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.analyzer.findings import finding_key
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project
from archmap.utils.file_utils import file_language_from_id, normalize_file_id


def normalize_report(report: dict) -> dict:
    """Bring a report to the in-memory shape ``diff_reports`` expects.

    ``archmap analyze --out`` writes ``nodes``/``edges`` as plain id lists and
    puts the full node and edge objects under ``detailed``. Reports already in
    the in-memory shape (full objects at the top level) are returned as is.
    """
    detailed = report.get("detailed")
    if not isinstance(detailed, dict):
        return report
    normalized = {key: value for key, value in report.items() if key != "detailed"}
    normalized["simple"] = {
        "nodes": list(report.get("nodes", [])),
        "edges": [list(edge) for edge in report.get("edges", [])],
    }
    normalized["nodes"] = list(detailed.get("nodes", []))
    normalized["edges"] = list(detailed.get("edges", []))
    return normalized


def load_snapshot(path: str | Path) -> dict:
    """Read a JSON report written by ``archmap analyze --out`` for ``diff``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_report(data)


def analyze_git_ref(project_root: str | Path, ref: str) -> dict:
    root = Path(project_root).resolve()
    virtual_files = _load_git_files(root, ref)
    config = load_project_config(root, virtual_files)

    parsed = parse_project(root, virtual_files=virtual_files, config=config)
    graph = build_graph(parsed)
    analyzed = analyze_graph(
        graph,
        layer_order=config["risks"]["layer_order"],
        forbidden_rules=config["architecture"]["rules"]["forbid"],
        allowed_rules=config["architecture"]["rules"]["allow"],
    )
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
    base_architecture = base_report.get("architecture", {})
    head_architecture = head_report.get("architecture", {})
    file_diff = _build_file_diff(base_report, head_report)

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
        "files": file_diff,
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
        "architecture": {
            "baseHealth": int(base_architecture.get("health", {}).get("score", 100)),
            "headHealth": int(head_architecture.get("health", {}).get("score", 100)),
            "healthDelta": int(head_architecture.get("health", {}).get("score", 100))
            - int(base_architecture.get("health", {}).get("score", 100)),
            "baseStyle": base_architecture.get("detectedStyle", {}).get("name", "unknown"),
            "headStyle": head_architecture.get("detectedStyle", {}).get("name", "unknown"),
            "styleChanged": base_architecture.get("detectedStyle", {}).get("name")
            != head_architecture.get("detectedStyle", {}).get("name"),
            "ruleViolationsDelta": len(head_architecture.get("ruleViolations", []))
            - len(base_architecture.get("ruleViolations", [])),
        },
        "grades": {
            "base": base_architecture.get("health", {}).get("grade"),
            "head": head_architecture.get("health", {}).get("grade"),
        },
        **_diff_findings(base_report, head_report),
        "tests": _diff_tests(base_report, head_report),
    }


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _sorted_findings(findings: list[dict]) -> list[dict]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_RANK.get(str(f.get("severity")), 5), finding_key(f)),
    )


def _diff_findings(base_report: dict, head_report: dict) -> dict:
    """New/resolved findings matched by key; only when both reports carry findings."""
    base_findings = base_report.get("findings")
    head_findings = head_report.get("findings")
    if not isinstance(base_findings, list) or not isinstance(head_findings, list):
        return {"findingsComparable": False}

    base_by_key = {finding_key(f): f for f in base_findings}
    head_by_key = {finding_key(f): f for f in head_findings}
    new = _sorted_findings([f for k, f in head_by_key.items() if k not in base_by_key])
    resolved = _sorted_findings([f for k, f in base_by_key.items() if k not in head_by_key])
    return {
        "findingsComparable": True,
        "findings": {
            "new": new,
            "resolved": resolved,
            "unchanged": len(base_by_key.keys() & head_by_key.keys()),
        },
        "bottlenecks": {
            "new": [f for f in new if f.get("category") == "structural_bottleneck"],
        },
    }


def _tested_ratio(report: dict) -> float | None:
    mapping = report.get("metrics", {}).get("testMapping")
    if not isinstance(mapping, dict):
        return None
    ratio = mapping.get("testedRatio")
    return float(ratio) if isinstance(ratio, (int, float)) else None


def _diff_tests(base_report: dict, head_report: dict) -> dict:
    """Tested-file ratio on each side and files whose tests disappeared."""
    base_files = _file_node_map(base_report)
    head_files = _file_node_map(head_report)
    lost = []
    for file_id in sorted(base_files.keys() & head_files.keys()):
        before = base_files[file_id].get("testedBy") or []
        after = head_files[file_id].get("testedBy") or []
        if before and not after:
            lost.append({"file": file_id, "testedBy": list(before)})
    return {
        "baseTestedRatio": _tested_ratio(base_report),
        "headTestedRatio": _tested_ratio(head_report),
        "lostCoverage": lost,
    }


def _average_complexity(report: dict) -> float:
    complexity_entries = report["metrics"].get("complexity", [])
    if not complexity_entries:
        return 0.0
    total = sum(float(entry.get("score", 0.0)) for entry in complexity_entries)
    return total / len(complexity_entries)


def _load_git_files(project_root: Path, ref: str) -> dict[str, str]:
    ls_tree = _run_git_bytes(project_root, ["ls-tree", "-r", "-z", "--name-only", ref])
    file_ids = [
        normalize_file_id(chunk.decode("utf-8", errors="replace"))
        for chunk in ls_tree.split(b"\0")
        if chunk
    ]
    target_file_ids = [
        file_id
        for file_id in file_ids
        if file_language_from_id(file_id) is not None or file_id in CONFIG_FILENAMES
    ]

    return _read_git_files_batch(project_root, ref, target_file_ids)


_GIT_TIMEOUT_SECONDS = 120


def _run_git(project_root: Path, args: list[str], allow_failure: bool = False) -> str | None:
    try:
        process = subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        if allow_failure:
            return None
        raise RuntimeError(f"git command timed out after {_GIT_TIMEOUT_SECONDS}s") from exc
    if process.returncode == 0:
        return process.stdout
    if allow_failure:
        return None
    raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "git command failed")


def _run_git_bytes(project_root: Path, args: list[str]) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git command timed out after {_GIT_TIMEOUT_SECONDS}s") from exc
    if process.returncode == 0:
        return process.stdout
    raise RuntimeError(
        process.stderr.decode("utf-8", errors="replace").strip()
        or process.stdout.decode("utf-8", errors="replace").strip()
        or "git command failed"
    )


def _read_git_files_batch(project_root: Path, ref: str, file_ids: list[str]) -> dict[str, str]:
    if not file_ids:
        return {}

    requests = "".join(f"{ref}:{file_id}\n" for file_id in file_ids).encode("utf-8")
    process = subprocess.Popen(
        ["git", "-C", str(project_root), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(requests, timeout=_GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise RuntimeError(f"git cat-file timed out after {_GIT_TIMEOUT_SECONDS}s") from exc
    if process.returncode != 0:
        raise RuntimeError(
            stderr.decode("utf-8", errors="replace").strip()
            or stdout.decode("utf-8", errors="replace").strip()
            or "git command failed"
        )

    files: dict[str, str] = {}
    offset = 0
    for file_id in file_ids:
        newline_index = stdout.find(b"\n", offset)
        if newline_index == -1:
            break

        header = stdout[offset:newline_index].decode("utf-8", errors="replace")
        offset = newline_index + 1

        if header.endswith(" missing"):
            continue

        header_parts = header.split()
        if len(header_parts) < 3:
            continue

        size = int(header_parts[2])
        payload = stdout[offset : offset + size]
        offset += size
        if offset < len(stdout) and stdout[offset : offset + 1] == b"\n":
            offset += 1

        files[file_id] = payload.decode("utf-8", errors="replace")

    return files


def _build_file_diff(base_report: dict, head_report: dict) -> dict:
    base_files = _file_node_map(base_report)
    head_files = _file_node_map(head_report)
    base_ids = set(base_files)
    head_ids = set(head_files)

    added = sorted(head_ids - base_ids)
    removed = sorted(base_ids - head_ids)
    shared = sorted(base_ids & head_ids)

    base_edges_by_source = _edges_by_source(base_report)
    head_edges_by_source = _edges_by_source(head_report)
    base_risk_scores = _risk_scores_by_file(base_report)
    head_risk_scores = _risk_scores_by_file(head_report)

    changed: list[dict] = []
    for file_id in shared:
        base_node = base_files[file_id]
        head_node = head_files[file_id]

        base_dependencies = base_edges_by_source.get(file_id, set())
        head_dependencies = head_edges_by_source.get(file_id, set())
        added_dependencies = sorted(head_dependencies - base_dependencies)
        removed_dependencies = sorted(base_dependencies - head_dependencies)

        outgoing_delta = int(head_node.get("outgoing", 0)) - int(base_node.get("outgoing", 0))
        incoming_delta = int(head_node.get("incoming", 0)) - int(base_node.get("incoming", 0))
        total_delta = (
            int(head_node.get("complexityConnections", 0))
            - int(base_node.get("complexityConnections", 0))
        )
        complexity_delta = float(head_node.get("complexityScore", 0.0)) - float(
            base_node.get("complexityScore", 0.0)
        )
        risk_delta = int(head_risk_scores.get(file_id, 0)) - int(base_risk_scores.get(file_id, 0))

        if (
            outgoing_delta == 0
            and incoming_delta == 0
            and total_delta == 0
            and abs(complexity_delta) < 1e-12
            and risk_delta == 0
            and not added_dependencies
            and not removed_dependencies
        ):
            continue

        changed.append(
            {
                "file": file_id,
                "outgoingDelta": outgoing_delta,
                "incomingDelta": incoming_delta,
                "totalConnectionsDelta": total_delta,
                "complexityDelta": round(complexity_delta, 6),
                "riskScoreDelta": risk_delta,
                "addedDependencies": added_dependencies,
                "removedDependencies": removed_dependencies,
            }
        )

    changed.sort(
        key=lambda item: (
            -(
                abs(item["riskScoreDelta"])
                + abs(item["totalConnectionsDelta"])
                + len(item["addedDependencies"])
                + len(item["removedDependencies"])
            ),
            item["file"],
        )
    )

    return {
        "added": added,
        "removed": removed,
        "changed": changed[:25],
        "delta": len(added) - len(removed),
    }


def _file_node_map(report: dict) -> dict[str, dict]:
    return {
        node["id"]: node
        for node in report.get("nodes", [])
        if node.get("type") == "file"
    }


def _edges_by_source(report: dict) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for edge in report.get("edges", []):
        grouped.setdefault(edge["source"], set()).add(edge["target"])
    return grouped


def _risk_scores_by_file(report: dict) -> dict[str, int]:
    return {
        item["file"]: int(item.get("riskScore", 0))
        for item in report.get("risks", {}).get("top_risk_files", [])
    }
