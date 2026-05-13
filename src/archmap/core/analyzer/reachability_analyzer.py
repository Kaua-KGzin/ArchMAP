from __future__ import annotations

from collections import deque
from typing import Any

from archmap.utils.file_utils import normalize_file_id


def trace_reachability(
    report: dict[str, Any],
    entrypoint: str,
    max_depth: int | None = None,
) -> dict:
    file_nodes = {
        node["id"]: node
        for node in report.get("nodes", [])
        if node.get("type") == "file"
    }

    outgoing: dict[str, set[str]] = {fid: set() for fid in file_nodes}
    for edge in report.get("edges", []):
        src = str(edge.get("source", ""))
        tgt = str(edge.get("target", ""))
        if src in outgoing and tgt in file_nodes:
            outgoing[src].add(tgt)

    norm_entry = _resolve_entrypoint(entrypoint, file_nodes)
    if norm_entry is None:
        return {
            "error": f"Entrypoint not found in analyzed project: {entrypoint}",
            "entrypoint": entrypoint,
            "reachable": [],
            "unreachable": sorted(file_nodes.keys()),
            "reachableCount": 0,
            "unreachableCount": len(file_nodes),
            "totalFiles": len(file_nodes),
            "coveragePercent": 0.0,
        }

    visited: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(norm_entry, 0)])
    while queue:
        current, depth = queue.popleft()
        if current in visited:
            continue
        if max_depth is not None and depth > max_depth:
            continue
        visited[current] = depth
        for neighbor in outgoing.get(current, set()):
            if neighbor not in visited:
                queue.append((neighbor, depth + 1))

    all_files = set(file_nodes.keys())
    unreachable = sorted(all_files - set(visited.keys()))
    reachable_sorted = sorted(visited.items(), key=lambda x: (x[1], x[0]))

    return {
        "entrypoint": norm_entry,
        "reachableCount": len(visited),
        "unreachableCount": len(unreachable),
        "totalFiles": len(all_files),
        "coveragePercent": round(len(visited) / max(len(all_files), 1) * 100, 1),
        "reachable": [{"file": fid, "depth": d} for fid, d in reachable_sorted],
        "unreachable": unreachable,
    }


def _resolve_entrypoint(entrypoint: str, file_nodes: dict) -> str | None:
    if entrypoint in file_nodes:
        return entrypoint

    norm = normalize_file_id(entrypoint)
    if norm in file_nodes:
        return norm

    for fid in file_nodes:
        if fid.endswith("/" + norm):
            return fid

    basename = norm.rsplit("/", 1)[-1]
    matches = [fid for fid in file_nodes if fid == basename or fid.endswith("/" + basename)]
    if len(matches) == 1:
        return matches[0]

    return None
