from __future__ import annotations

from collections import deque


def find_circular_dependencies(
    file_node_ids: list[str], adjacency: dict[str, list[str]]
) -> list[list[str]]:
    components: list[list[str]] = []
    reverse_adjacency = _build_reverse_adjacency(file_node_ids, adjacency)
    finish_order = _compute_finish_order(file_node_ids, adjacency)
    visited: set[str] = set()

    for node_id in reversed(finish_order):
        if node_id in visited:
            continue

        component = _collect_component(node_id, reverse_adjacency, visited)
        if len(component) > 1:
            components.append(sorted(component))
            continue

        only_node = component[0]
        if only_node in adjacency.get(only_node, []):
            components.append(component)

    return sorted(components, key=lambda item: item[0])


def find_cycle_path(cycle_members: list[str], adjacency: dict[str, list[str]]) -> list[str]:
    """Return a concrete directed cycle path (first node repeated at end) within the SCC."""
    if not cycle_members:
        return []

    members_set = set(cycle_members)
    start = cycle_members[0]

    # BFS: find shortest path from start back to start through SCC members
    queue: deque[list[str]] = deque([[start]])
    visited: set[str] = set()

    while queue:
        path = queue.popleft()
        current = path[-1]

        for neighbor in adjacency.get(current, []):
            if neighbor not in members_set:
                continue
            if neighbor == start and len(path) > 1:
                return path + [start]
            if neighbor in visited or neighbor in set(path):
                continue
            visited.add(neighbor)
            queue.append(path + [neighbor])

    # Fallback: return members as a closed list (should not normally happen for a valid SCC)
    return list(cycle_members) + [cycle_members[0]]


def suggest_cycle_break(
    cycle_members: list[str],
    cycle_path: list[str],
    incoming_counts: dict[str, int],
) -> dict | None:
    """Identify the best edge to remove to break the cycle.

    Prefers the edge (a → b) where b has the fewest external incoming dependencies,
    making b the easiest module to extract or invert.
    """
    if len(cycle_path) < 3:
        return None

    path_edges = list(zip(cycle_path[:-1], cycle_path[1:], strict=False))
    if not path_edges:
        return None

    best_from, best_to = min(path_edges, key=lambda e: incoming_counts.get(e[1], 0))
    incoming = incoming_counts.get(best_to, 0)
    return {
        "from": best_from,
        "to": best_to,
        "reason": (
            f"'{best_to}' has {incoming} incoming dependenc{'y' if incoming == 1 else 'ies'} — "
            "consider extracting an interface or inverting this dependency"
        ),
    }


def enrich_cycles(
    cycles: list[list[str]],
    adjacency: dict[str, list[str]],
    incoming_counts: dict[str, int],
) -> list[dict]:
    """Return enriched cycle objects with path and break suggestion."""
    enriched: list[dict] = []
    for members in cycles:
        path = find_cycle_path(members, adjacency)
        break_suggestion = suggest_cycle_break(members, path, incoming_counts)
        enriched.append(
            {
                "members": members,
                "path": path,
                "size": len(members),
                "breakSuggestion": break_suggestion,
            }
        )
    return enriched


def _compute_finish_order(
    file_node_ids: list[str], adjacency: dict[str, list[str]]
) -> list[str]:
    visited: set[str] = set()
    finish_order: list[str] = []

    for start_node in file_node_ids:
        if start_node in visited:
            continue

        stack: list[tuple[str, bool]] = [(start_node, False)]
        while stack:
            node_id, expanded = stack.pop()
            if expanded:
                finish_order.append(node_id)
                continue

            if node_id in visited:
                continue

            visited.add(node_id)
            stack.append((node_id, True))

            neighbors = adjacency.get(node_id, [])
            for neighbor in reversed(neighbors):
                if neighbor not in visited:
                    stack.append((neighbor, False))

    return finish_order


def _build_reverse_adjacency(
    file_node_ids: list[str], adjacency: dict[str, list[str]]
) -> dict[str, list[str]]:
    reverse_adjacency = {node_id: [] for node_id in file_node_ids}

    for source, targets in adjacency.items():
        for target in targets:
            if target in reverse_adjacency:
                reverse_adjacency[target].append(source)

    return reverse_adjacency


def _collect_component(
    start_node: str,
    reverse_adjacency: dict[str, list[str]],
    visited: set[str],
) -> list[str]:
    component: list[str] = []
    stack = [start_node]
    visited.add(start_node)

    while stack:
        node_id = stack.pop()
        component.append(node_id)

        for neighbor in reverse_adjacency.get(node_id, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            stack.append(neighbor)

    return component
