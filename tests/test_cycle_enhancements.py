from __future__ import annotations

from archmap.core.analyzer.cycle_detector import (
    enrich_cycles,
    find_circular_dependencies,
    find_cycle_path,
    suggest_cycle_break,
)


def test_find_cycle_path_simple_two_node():
    members = ["a", "b"]
    adjacency = {"a": ["b"], "b": ["a"]}
    path = find_cycle_path(members, adjacency)
    assert path[0] == path[-1], "path should start and end at the same node"
    assert len(path) >= 3


def test_find_cycle_path_triangle():
    members = ["a", "b", "c"]
    adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
    path = find_cycle_path(members, adjacency)
    assert path[0] == path[-1]
    # All three members appear in the path
    assert set(path[:-1]) == {"a", "b", "c"}


def test_find_cycle_path_self_loop():
    members = ["x"]
    adjacency = {"x": ["x"]}
    path = find_cycle_path(members, adjacency)
    assert path[0] == path[-1]
    assert "x" in path


def test_find_cycle_path_empty():
    assert find_cycle_path([], {}) == []


def test_find_cycle_path_returns_valid_directed_path():
    members = ["a", "b", "c"]
    adjacency = {"a": ["b", "c"], "b": ["c"], "c": ["a"]}
    path = find_cycle_path(members, adjacency)
    # Consecutive nodes in path must be valid directed edges
    for src, tgt in zip(path[:-1], path[1:], strict=False):
        assert tgt in adjacency.get(src, [])


def test_suggest_cycle_break_picks_lowest_incoming():
    members = ["a", "b", "c"]
    cycle_path = ["a", "b", "c", "a"]
    # b has 3 incoming, c has 1 incoming → prefer breaking a→b or b→c
    # With incoming_counts: a=2, b=3, c=1 → best target to break TO is c (1)
    incoming_counts = {"a": 2, "b": 3, "c": 1}
    result = suggest_cycle_break(members, cycle_path, incoming_counts)
    assert result is not None
    assert result["to"] == "c"
    assert "from" in result
    assert "reason" in result


def test_suggest_cycle_break_returns_none_for_short_path():
    result = suggest_cycle_break(["a"], ["a"], {})
    assert result is None


def test_suggest_cycle_break_reason_contains_filename():
    members = ["x", "y"]
    path = ["x", "y", "x"]
    result = suggest_cycle_break(members, path, {"x": 5, "y": 2})
    assert result is not None
    assert result["to"] in result["reason"]


def test_enrich_cycles_structure():
    cycles = [["a", "b"], ["c", "d", "e"]]
    adjacency = {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["e"], "e": ["c"]}
    incoming_counts = {"a": 1, "b": 2, "c": 1, "d": 1, "e": 3}
    enriched = enrich_cycles(cycles, adjacency, incoming_counts)

    assert len(enriched) == 2
    for item in enriched:
        assert "members" in item
        assert "path" in item
        assert "size" in item
        assert "breakSuggestion" in item
        assert item["size"] == len(item["members"])


def test_enrich_cycles_path_is_valid_cycle():
    cycles = [["a", "b", "c"]]
    adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
    incoming_counts = {"a": 1, "b": 1, "c": 1}
    enriched = enrich_cycles(cycles, adjacency, incoming_counts)

    path = enriched[0]["path"]
    assert path[0] == path[-1]


def test_enrich_cycles_empty():
    assert enrich_cycles([], {}, {}) == []


def test_find_circular_dependencies_still_returns_lists():
    """Ensure original function still returns list-of-lists (backward compat)."""
    node_ids = ["a", "b", "c"]
    adjacency = {"a": ["b"], "b": ["a"], "c": []}
    cycles = find_circular_dependencies(node_ids, adjacency)
    assert isinstance(cycles, list)
    for cycle in cycles:
        assert isinstance(cycle, list)


def test_enrich_cycles_break_suggestion_is_in_cycle():
    """The suggested break edge must be between two nodes in the cycle."""
    cycles = [["a", "b", "c"]]
    adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
    incoming_counts = {"a": 1, "b": 2, "c": 3}
    enriched = enrich_cycles(cycles, adjacency, incoming_counts)

    suggestion = enriched[0]["breakSuggestion"]
    members_set = set(enriched[0]["members"])
    assert suggestion["from"] in members_set
    assert suggestion["to"] in members_set
