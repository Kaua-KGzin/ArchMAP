"""Tests for reachability_analyzer — BFS from an entrypoint."""

from __future__ import annotations

import pytest

from archmap.core.analyzer.reachability_analyzer import _resolve_entrypoint, trace_reachability


def _make_report(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges}


def _file(fid: str) -> dict:
    return {"id": fid, "type": "file", "label": fid}


# ---------------------------------------------------------------------------
# trace_reachability — happy path
# ---------------------------------------------------------------------------


def test_trace_simple_chain() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py"), _file("c.py")],
        edges=[
            {"source": "a.py", "target": "b.py"},
            {"source": "b.py", "target": "c.py"},
        ],
    )
    result = trace_reachability(report, "a.py")
    assert result["entrypoint"] == "a.py"
    assert result["reachableCount"] == 3
    assert result["unreachableCount"] == 0
    assert result["coveragePercent"] == 100.0
    reachable_files = [r["file"] for r in result["reachable"]]
    assert "a.py" in reachable_files
    assert "b.py" in reachable_files
    assert "c.py" in reachable_files


def test_trace_with_unreachable() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py"), _file("isolated.py")],
        edges=[{"source": "a.py", "target": "b.py"}],
    )
    result = trace_reachability(report, "a.py")
    assert result["reachableCount"] == 2
    assert result["unreachableCount"] == 1
    assert "isolated.py" in result["unreachable"]
    assert result["coveragePercent"] == pytest.approx(66.7, abs=0.1)


def test_trace_max_depth() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py"), _file("c.py")],
        edges=[
            {"source": "a.py", "target": "b.py"},
            {"source": "b.py", "target": "c.py"},
        ],
    )
    result = trace_reachability(report, "a.py", max_depth=1)
    # depth 0: a.py, depth 1: b.py — c.py is at depth 2, excluded
    reachable_files = [r["file"] for r in result["reachable"]]
    assert "a.py" in reachable_files
    assert "b.py" in reachable_files
    assert "c.py" not in reachable_files


def test_trace_entrypoint_not_found() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py")],
        edges=[{"source": "a.py", "target": "b.py"}],
    )
    result = trace_reachability(report, "nonexistent.py")
    assert "error" in result
    assert result["reachableCount"] == 0
    assert result["coveragePercent"] == 0.0
    assert set(result["unreachable"]) == {"a.py", "b.py"}


def test_trace_empty_report() -> None:
    result = trace_reachability({"nodes": [], "edges": []}, "a.py")
    assert "error" in result


def test_trace_single_node_no_edges() -> None:
    report = _make_report(nodes=[_file("main.py")], edges=[])
    result = trace_reachability(report, "main.py")
    assert result["reachableCount"] == 1
    assert result["unreachableCount"] == 0
    assert result["coveragePercent"] == 100.0


def test_trace_ignores_non_file_nodes() -> None:
    report = _make_report(
        nodes=[
            _file("a.py"),
            {"id": "pkg:requests", "type": "package", "label": "requests"},
        ],
        edges=[{"source": "a.py", "target": "pkg:requests"}],
    )
    result = trace_reachability(report, "a.py")
    # pkg:requests is not a file node, should not appear in reachable
    assert result["reachableCount"] == 1
    assert result["totalFiles"] == 1


def test_trace_cycle_does_not_loop() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py")],
        edges=[
            {"source": "a.py", "target": "b.py"},
            {"source": "b.py", "target": "a.py"},
        ],
    )
    result = trace_reachability(report, "a.py")
    assert result["reachableCount"] == 2


def test_trace_depth_metadata() -> None:
    report = _make_report(
        nodes=[_file("a.py"), _file("b.py"), _file("c.py")],
        edges=[
            {"source": "a.py", "target": "b.py"},
            {"source": "b.py", "target": "c.py"},
        ],
    )
    result = trace_reachability(report, "a.py")
    depth_map = {r["file"]: r["depth"] for r in result["reachable"]}
    assert depth_map["a.py"] == 0
    assert depth_map["b.py"] == 1
    assert depth_map["c.py"] == 2


# ---------------------------------------------------------------------------
# _resolve_entrypoint
# ---------------------------------------------------------------------------


def test_resolve_exact_match() -> None:
    nodes = {"src/app.py": {}, "src/main.py": {}}
    assert _resolve_entrypoint("src/app.py", nodes) == "src/app.py"


def test_resolve_normalized_path() -> None:
    nodes = {"src/app.py": {}}
    assert _resolve_entrypoint("src\\app.py", nodes) == "src/app.py"


def test_resolve_suffix_match() -> None:
    nodes = {"project/src/app.py": {}}
    assert _resolve_entrypoint("src/app.py", nodes) == "project/src/app.py"


def test_resolve_basename_unique() -> None:
    nodes = {"project/src/app.py": {}}
    assert _resolve_entrypoint("app.py", nodes) == "project/src/app.py"


def test_resolve_basename_ambiguous() -> None:
    # When multiple files end with "/app.py", the suffix loop returns the first match
    nodes = {"src/app.py": {}, "tests/app.py": {}}
    result = _resolve_entrypoint("app.py", nodes)
    assert result in ("src/app.py", "tests/app.py")


def test_resolve_not_found() -> None:
    nodes = {"src/app.py": {}}
    assert _resolve_entrypoint("ghost.py", nodes) is None
