from __future__ import annotations

from archmap.core.analyzer.cycle_detector import find_circular_dependencies


def test_find_circular_dependencies_handles_deep_acyclic_chain() -> None:
    node_count = 3000
    file_node_ids = [f"node_{index}.py" for index in range(node_count)]
    adjacency = {node_id: [] for node_id in file_node_ids}

    for index in range(node_count - 1):
        adjacency[file_node_ids[index]].append(file_node_ids[index + 1])

    assert find_circular_dependencies(file_node_ids, adjacency) == []


def test_find_circular_dependencies_handles_large_cycle_iteratively() -> None:
    node_count = 1500
    file_node_ids = [f"node_{index}.py" for index in range(node_count)]
    adjacency = {node_id: [] for node_id in file_node_ids}

    for index in range(node_count - 1):
        adjacency[file_node_ids[index]].append(file_node_ids[index + 1])
    adjacency[file_node_ids[-1]].append(file_node_ids[0])

    cycles = find_circular_dependencies(file_node_ids, adjacency)

    assert len(cycles) == 1
    assert len(cycles[0]) == node_count
    assert cycles[0][0] == "node_0.py"
    assert f"node_{node_count - 1}.py" in cycles[0]
