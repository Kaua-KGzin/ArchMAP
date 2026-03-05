from __future__ import annotations


def find_circular_dependencies(
    file_node_ids: list[str], adjacency: dict[str, list[str]]
) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def strong_connect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1

        stack.append(node_id)
        on_stack.add(node_id)

        for neighbor in adjacency.get(node_id, []):
            if neighbor not in indices:
                strong_connect(neighbor)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[neighbor])

        if lowlinks[node_id] != indices[node_id]:
            return

        component: list[str] = []
        while stack:
            current = stack.pop()
            on_stack.discard(current)
            component.append(current)
            if current == node_id:
                break

        if len(component) > 1:
            components.append(sorted(component))
            return

        only_node = component[0]
        if only_node in adjacency.get(only_node, []):
            components.append(component)

    for node_id in file_node_ids:
        if node_id not in indices:
            strong_connect(node_id)

    return sorted(components, key=lambda item: item[0])
