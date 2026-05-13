from __future__ import annotations


def calculate_impact(node_id: str, edges: list[dict]) -> dict:
    # Build backward adjacency list (target -> list of sources)
    # If source depends on target, target impacts source.
    dependents_map: dict[str, list[str]] = {}
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        dependents_map.setdefault(target, []).append(source)

    impacted = set()
    queue = [node_id]
    visited = {node_id}

    while queue:
        current = queue.pop(0)
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
        "impactedFiles": sorted(list(impacted)),
        "impactCount": count,
        "risk": risk
    }
