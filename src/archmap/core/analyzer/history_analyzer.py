from __future__ import annotations

from pathlib import Path

from archmap.core.analyzer.diff_analyzer import _run_git, analyze_git_ref
from archmap.utils.file_utils import normalize_file_id

HISTORY_LOG_FORMAT = "%H%x1f%h%x1f%an%x1f%ae%x1f%ct%x1f%cI%x1f%s"


def analyze_git_history(
    project_root: str | Path,
    ref: str = "HEAD",
    limit: int = 12,
) -> dict:
    root = Path(project_root).resolve()
    commits = _list_history_commits(root, ref, limit)
    if not commits:
        return {
            "repoRoot": str(root),
            "ref": ref,
            "windowSize": 0,
            "snapshots": [],
            "trend": _empty_trend(),
            "cycles": [],
            "hotspots": [],
        }

    reports: list[dict] = []
    snapshots: list[dict] = []
    for commit in commits:
        report = analyze_git_ref(root, commit["commit"])
        report["ref"] = commit["commit"]
        reports.append(report)
        snapshots.append(_snapshot_from_report(commit, report))

    current_report = reports[-1]
    cycle_history = _build_cycle_history(commits, reports, root)
    hotspots = _build_hotspot_history(root, current_report)

    return {
        "repoRoot": str(root),
        "ref": ref,
        "windowSize": len(snapshots),
        "snapshots": snapshots,
        "trend": _build_trend(snapshots),
        "cycles": cycle_history,
        "hotspots": hotspots,
    }


def _list_history_commits(project_root: Path, ref: str, limit: int) -> list[dict]:
    max_count = max(1, int(limit))
    output = _run_git(
        project_root,
        [
            "log",
            "--reverse",
            f"--max-count={max_count}",
            f"--format={HISTORY_LOG_FORMAT}",
            ref,
        ],
        allow_failure=True,
    )
    if not output:
        return []

    commits: list[dict] = []
    for line in output.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 7:
            continue
        commits.append(
            {
                "commit": parts[0],
                "shortCommit": parts[1],
                "author": parts[2],
                "email": parts[3],
                "timestamp": int(parts[4]),
                "committedAt": parts[5],
                "subject": parts[6],
            }
        )

    return commits


def _snapshot_from_report(commit: dict, report: dict) -> dict:
    metrics = report.get("metrics", {})
    architecture = report.get("architecture", {})
    health = architecture.get("health", {})
    complexity = metrics.get("complexity", [])
    average_instability = metrics.get("coupling", {}).get("averageInstability", 0.0)

    return {
        **commit,
        "files": int(metrics.get("filesAnalyzed", 0)),
        "dependencies": int(metrics.get("totalDependencies", 0)),
        "cycles": int(metrics.get("circularDependencyCount", 0)),
        "health": int(health.get("score", 100)),
        "grade": health.get("grade", "?"),
        "style": architecture.get("detectedStyle", {}).get("name", "unknown"),
        "ruleViolations": len(architecture.get("ruleViolations", [])),
        "averageComplexity": round(_average_complexity(complexity), 6),
        "averageInstability": round(float(average_instability), 6),
        "regression": False, # Will be set during trend analysis
    }


def _average_complexity(entries: list[dict]) -> float:
    if not entries:
        return 0.0
    return sum(float(entry.get("score", 0.0)) for entry in entries) / len(entries)


def _build_trend(snapshots: list[dict]) -> dict:
    if not snapshots:
        return _empty_trend()

    first = snapshots[0]
    last = snapshots[-1]
    return {
        "healthDelta": int(last["health"]) - int(first["health"]),
        "cycleDelta": int(last["cycles"]) - int(first["cycles"]),
        "dependencyDelta": int(last["dependencies"]) - int(first["dependencies"]),
        "ruleViolationsDelta": int(last["ruleViolations"]) - int(first["ruleViolations"]),
        "complexityDeltaPercent": _delta_percent(
            float(first["averageComplexity"]),
            float(last["averageComplexity"]),
        ),
        "instabilityDeltaPercent": _delta_percent(
            float(first["averageInstability"]),
            float(last["averageInstability"]),
        ),
        "fromStyle": first["style"],
        "toStyle": last["style"],
        "styleChanged": first["style"] != last["style"],
        "regressions": _find_regressions(snapshots),
    }


def _build_cycle_history(
    commits: list[dict],
    reports: list[dict],
    project_root: Path,
) -> list[dict]:
    if not reports:
        return []

    current_report = reports[-1]
    current_cycles = current_report.get("cycles", [])
    if not current_cycles:
        return []

    cycle_snapshots = [_cycle_map(report.get("cycles", [])) for report in reports]
    history: list[dict] = []
    for cycle in current_cycles:
        cycle_key = _canonical_cycle(cycle)
        introduced_index = next(
            (
                index
                for index, snapshot_map in enumerate(cycle_snapshots)
                if cycle_key in snapshot_map
            ),
            len(commits) - 1,
        )
        introduced_commit = commits[introduced_index]
        contributors = _collect_file_history(project_root, cycle)
        suspected_owner = max(
            contributors,
            key=lambda item: (int(item.get("timestamp", 0)), item.get("file", "")),
            default=None,
        )
        history.append(
            {
                "cycle": cycle,
                "cycleKey": cycle_key,
                "introducedIn": introduced_commit,
                "ageCommits": len(commits) - int(introduced_index),
                "suspectedOwner": suspected_owner,
                "contributors": contributors,
            }
        )

    history.sort(
        key=lambda item: (
            -int(item["ageCommits"]),
            item["cycleKey"],
        )
    )
    return history


def _build_hotspot_history(project_root: Path, report: dict) -> list[dict]:
    hotspots: list[dict] = []
    for risk_item in report.get("risks", {}).get("top_risk_files", [])[:5]:
        file_id = normalize_file_id(risk_item["file"])
        last_touched = _latest_file_commit(project_root, file_id)
        hotspots.append(
            {
                "file": file_id,
                "riskScore": int(risk_item.get("riskScore", 0)),
                "signals": list(risk_item.get("signals", [])),
                "lastTouched": last_touched,
            }
        )

    return hotspots


def _cycle_map(cycles: list[list[str]]) -> dict[str, list[str]]:
    return {
        _canonical_cycle(cycle): cycle
        for cycle in cycles
        if cycle
    }


def _canonical_cycle(cycle: list[str]) -> str:
    normalized = [normalize_file_id(entry) for entry in cycle if entry]
    if not normalized:
        return ""

    variants: list[list[str]] = []
    for sequence in (normalized, list(reversed(normalized))):
        for index in range(len(sequence)):
            variants.append(sequence[index:] + sequence[:index])

    best = min(variants)
    return " -> ".join(best)


def _collect_file_history(project_root: Path, file_ids: list[str]) -> list[dict]:
    history: list[dict] = []
    for file_id in sorted({normalize_file_id(file_id) for file_id in file_ids}):
        commit = _latest_file_commit(project_root, file_id)
        if commit is None:
            continue
        history.append({"file": file_id, **commit})
    return history


def _latest_file_commit(project_root: Path, file_id: str) -> dict | None:
    output = _run_git(
        project_root,
        [
            "log",
            "-1",
            f"--format={HISTORY_LOG_FORMAT}",
            "HEAD",
            "--",
            normalize_file_id(file_id),
        ],
        allow_failure=True,
    )
    if not output:
        return None

    parts = output.splitlines()[0].split("\x1f")
    if len(parts) != 7:
        return None

    return {
        "commit": parts[0],
        "shortCommit": parts[1],
        "author": parts[2],
        "email": parts[3],
        "timestamp": int(parts[4]),
        "committedAt": parts[5],
        "subject": parts[6],
    }


def _delta_percent(base_value: float, head_value: float) -> float:
    if base_value == 0:
        return 100.0 if head_value > 0 else 0.0
    return round(((head_value - base_value) / base_value) * 100, 2)


def _find_regressions(snapshots: list[dict]) -> list[dict]:
    regressions = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]

        health_drop = int(prev["health"]) - int(curr["health"])
        cycle_gain = int(curr["cycles"]) - int(prev["cycles"])

        if health_drop >= 10 or cycle_gain >= 5:
            curr["regression"] = True
            regressions.append(
                {
                    "commit": curr["shortCommit"],
                    "author": curr["author"],
                    "healthDrop": health_drop,
                    "newCycles": cycle_gain,
                    "message": curr["subject"],
                }
            )
    return regressions


def _empty_trend() -> dict:
    return {
        "healthDelta": 0,
        "cycleDelta": 0,
        "dependencyDelta": 0,
        "ruleViolationsDelta": 0,
        "complexityDeltaPercent": 0.0,
        "instabilityDeltaPercent": 0.0,
        "fromStyle": "unknown",
        "toStyle": "unknown",
        "styleChanged": False,
    }
