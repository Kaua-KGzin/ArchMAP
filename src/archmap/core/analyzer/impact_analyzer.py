from __future__ import annotations

from collections import deque


def build_dependents_map(edges: list[dict]) -> dict[str, list[str]]:
    """Build a backward adjacency map (target -> sources that depend on it).

    Computing this once and reusing it across every node turns whole-graph
    impact analysis from O(V * E) into O(V + E).  If ``source`` depends on
    ``target``, then ``target`` impacts ``source``.
    """
    dependents_map: dict[str, list[str]] = {}
    for edge in edges:
        dependents_map.setdefault(edge["target"], []).append(edge["source"])
    return dependents_map


def calculate_impact(
    node_id: str,
    edges: list[dict],
    dependents_map: dict[str, list[str]] | None = None,
) -> dict:
    """Return the transitive set of files impacted by a change to ``node_id``.

    ``dependents_map`` may be supplied (via :func:`build_dependents_map`) to
    avoid rebuilding the backward adjacency on every call; when omitted it is
    derived from ``edges`` for backward compatibility.
    """
    if dependents_map is None:
        dependents_map = build_dependents_map(edges)

    impacted: set[str] = set()
    visited = {node_id}
    queue: deque[str] = deque([node_id])

    while queue:
        current = queue.popleft()
        for dependent in dependents_map.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                impacted.add(dependent)
                queue.append(dependent)

    count = len(impacted)
    risk = "low"
    if count > 10:
        risk = "critical"
    elif count > 5:
        risk = "warning"
    elif count > 0:
        risk = "ok"

    return {
        "nodeId": node_id,
        "impactedFiles": sorted(impacted),
        "impactCount": count,
        "risk": risk,
    }
