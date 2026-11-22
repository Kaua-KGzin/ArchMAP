"""Betweenness centrality of the file dependency graph (structural bottlenecks)."""

from __future__ import annotations

import random
from collections import deque

import pytest

from archmap.core.analyzer.centrality import (
    betweenness_centrality,
    build_centrality_findings,
)


def _oracle(nodes, edges):
    """Independent formula: sum over s,t of sigma_sv * sigma_vt / sigma_st."""
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)

    def bfs(src):
        dist, sigma = {src: 0}, {src: 1}
        queue = deque([src])
        while queue:
            v = queue.popleft()
            for w in adj[v]:
                if w not in dist:
                    dist[w] = dist[v] + 1
                    sigma[w] = 0
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
        return dist, sigma

    info = {n: bfs(n) for n in nodes}
    # Normalised by the ordered pairs that are connected at all.
    connected = sum(len(info[s][0]) - 1 for s in nodes)
    scale = 1 / connected if connected else 0
    result = {}
    for v in nodes:
        total = 0.0
        for s in nodes:
            for t in nodes:
                if len({s, t, v}) < 3:
                    continue
                ds, ss = info[s]
                dv, sv = info[v]
                if t not in ds or v not in ds or t not in dv:
                    continue
                if ds[v] + dv[t] == ds[t]:
                    total += ss[v] * sv[t] / ss[t]
        result[v] = total * scale
    return result


def test_chain_middle_node_carries_the_only_path():
    scores, meta = betweenness_centrality(["a", "b", "c"], [("a", "b"), ("b", "c")])
    # Connected pairs: a->b, a->c, b->c; only a->c passes through b.
    assert scores == pytest.approx({"a": 0.0, "b": 1 / 3, "c": 0.0})
    assert meta["method"] == "exact"


def test_parallel_paths_split_the_credit():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
    scores, _ = betweenness_centrality(["a", "b", "c", "d"], edges)
    assert scores["b"] == pytest.approx(scores["c"])
    # Five connected pairs; b carries half of the two a->d chains.
    assert scores["b"] == pytest.approx(0.5 / 5)


@pytest.mark.parametrize("seed", range(8))
def test_matches_independent_formula_on_random_graphs(seed):
    rng = random.Random(seed)
    nodes = [f"f{i}" for i in range(12)]
    edges = sorted({(a, b) for a in nodes for b in nodes if a != b and rng.random() < 0.2})
    scores, _ = betweenness_centrality(nodes, edges)
    assert scores == pytest.approx(_oracle(nodes, edges))


def test_edges_to_unknown_nodes_are_ignored():
    scores, _ = betweenness_centrality(["a", "b", "c"], [("a", "b"), ("b", "c"), ("b", "pkg:x")])
    assert set(scores) == {"a", "b", "c"}
    assert scores["b"] == pytest.approx(1 / 3)


def test_large_graphs_are_sampled_deterministically():
    nodes = [f"f{i}" for i in range(60)]
    edges = [(f"f{i}", f"f{i + 1}") for i in range(59)]
    first, meta = betweenness_centrality(nodes, edges, exact_limit=20, samples=30)
    second, _ = betweenness_centrality(nodes, edges, exact_limit=20, samples=30)
    exact, _ = betweenness_centrality(nodes, edges)

    assert {k: meta[k] for k in ("method", "samples", "nodes")} == {
        "method": "sampled", "samples": 30, "nodes": 60,
    }
    assert first == second
    # A chain's betweenness is a flat parabola, so a sample puts the peak
    # somewhere in the middle third rather than exactly at f30.
    assert 20 <= int(max(first, key=first.get)[1:]) <= 40
    assert first["f30"] == pytest.approx(exact["f30"], rel=0.5)


_META = {"method": "exact", "nodes": 42, "connectedPairs": 500}


def test_findings_flag_files_on_a_large_share_of_chains():
    scores = {f"src/m{i}.py": 0.001 for i in range(40)}
    scores["src/hub.py"] = 0.31
    scores["src/next.py"] = 0.12
    scores["src/minor.py"] = 0.06
    findings = build_centrality_findings(scores, _META)

    assert [f["file"] for f in findings] == ["src/hub.py", "src/next.py"]
    hub = findings[0]
    assert hub["id"] == "GRAPH-001"
    assert hub["domain"] == "code"
    assert hub["category"] == "structural_bottleneck"
    assert "31.0%" in hub["message"]


def test_no_findings_for_sparse_or_flat_graphs():
    sparse = {**{f"m{i}": 0.0 for i in range(20)}, "hub": 0.5}
    assert build_centrality_findings(sparse, {**_META, "connectedPairs": 12}) == []
    assert build_centrality_findings({f"m{i}": 0.02 for i in range(50)}, _META) == []


def test_test_files_are_never_reported_as_bottlenecks():
    scores = {**{f"src/m{i}.py": 0.0 for i in range(20)}, "tests/helpers/factory.py": 0.4}
    assert build_centrality_findings(scores, _META) == []


def _project(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "api.py").write_text("from pkg import service\n")
    (pkg / "service.py").write_text("from pkg import repo\n")
    (pkg / "repo.py").write_text("X = 1\n")
    return tmp_path


def test_analysis_reports_betweenness_without_touching_risk(tmp_path):
    from archmap.core import analyze_project

    report = analyze_project(_project(tmp_path), use_cache=False)
    nodes = {n["id"]: n for n in report["nodes"] if n.get("type") == "file"}

    assert nodes["pkg/service.py"]["betweenness"] > nodes["pkg/api.py"]["betweenness"]
    centrality = report["metrics"]["centrality"]
    assert centrality["method"] == "exact"
    assert centrality["top"][0]["file"] == "pkg/service.py"
    for entry in report["risks"]["top_risk_files"]:
        assert "betweenness" not in entry
