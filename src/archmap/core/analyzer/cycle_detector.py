from __future__ import annotations


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
