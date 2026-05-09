from __future__ import annotations

from archmap.cli.commands import _filter_external


def _file_node(file_id: str, *, outgoing: int = 0, incoming: int = 0) -> dict:
    return {"id": file_id, "type": "file", "outgoing": outgoing, "incoming": incoming}


def _package_node(pkg_id: str) -> dict:
    return {"id": pkg_id, "type": "package", "outgoing": 0, "incoming": 0}


def _edge(source: str, target: str) -> dict:
    return {"id": f"{source}->{target}", "source": source, "target": target}


def _make_report(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "metrics": {
            "filesAnalyzed": sum(1 for n in nodes if n.get("type") == "file"),
            "totalDependencies": len(edges),
            "circularDependencyCount": 0,
            "resolutionRate": 1.0,
            "externalDependencies": sum(1 for n in nodes if n.get("type") == "package"),
            "complexity": [],
        },
        "nodes": nodes,
        "edges": edges,
        "risks": {},
        "architecture": {},
    }


def test_filter_external_removes_package_nodes() -> None:
    nodes = [_file_node("a.py"), _package_node("pkg:requests")]
    edges = [_edge("a.py", "pkg:requests")]
    filtered = _filter_external(_make_report(nodes, edges))
    assert all(n["type"] != "package" for n in filtered["nodes"])


def test_filter_external_removes_edges_to_packages() -> None:
    nodes = [_file_node("a.py"), _package_node("pkg:requests")]
    edges = [_edge("a.py", "pkg:requests")]
    filtered = _filter_external(_make_report(nodes, edges))
    assert filtered["edges"] == []


def test_filter_external_no_op_when_no_packages() -> None:
    nodes = [_file_node("a.py"), _file_node("b.py")]
    edges = [_edge("a.py", "b.py")]
    report = _make_report(nodes, edges)
    result = _filter_external(report)
    assert result is report


def test_filter_external_preserves_internal_edges() -> None:
    nodes = [_file_node("a.py"), _file_node("b.py"), _package_node("pkg:requests")]
    edges = [_edge("a.py", "b.py"), _edge("a.py", "pkg:requests")]
    filtered = _filter_external(_make_report(nodes, edges))
    assert len(filtered["edges"]) == 1
    assert filtered["edges"][0]["source"] == "a.py"
    assert filtered["edges"][0]["target"] == "b.py"


def test_filter_external_recomputes_outgoing_counts() -> None:
    nodes = [_file_node("a.py", outgoing=2), _file_node("b.py"), _package_node("pkg:requests")]
    edges = [_edge("a.py", "b.py"), _edge("a.py", "pkg:requests")]
    filtered = _filter_external(_make_report(nodes, edges))
    a = next(n for n in filtered["nodes"] if n["id"] == "a.py")
    assert a["outgoing"] == 1


def test_filter_external_resets_metrics() -> None:
    nodes = [_file_node("a.py"), _package_node("pkg:django")]
    edges = [_edge("a.py", "pkg:django")]
    filtered = _filter_external(_make_report(nodes, edges))
    assert filtered["metrics"]["externalDependencies"] == 0
    assert filtered["metrics"]["totalDependencies"] == 0


def test_filter_external_does_not_mutate_original() -> None:
    nodes = [_file_node("a.py"), _package_node("pkg:requests")]
    edges = [_edge("a.py", "pkg:requests")]
    report = _make_report(nodes, edges)
    _filter_external(report)
    assert any(n["type"] == "package" for n in report["nodes"])
    assert len(report["edges"]) == 1


def test_filter_external_keeps_all_file_nodes() -> None:
    nodes = [
        _file_node("a.py"),
        _file_node("b.py"),
        _file_node("c.py"),
        _package_node("pkg:requests"),
    ]
    edges = [_edge("a.py", "b.py"), _edge("b.py", "c.py"), _edge("c.py", "pkg:requests")]
    filtered = _filter_external(_make_report(nodes, edges))
    file_ids = {n["id"] for n in filtered["nodes"]}
    assert file_ids == {"a.py", "b.py", "c.py"}
