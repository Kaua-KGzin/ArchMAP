"""Whole-graph impact analysis: SCC condensation, exactness and list cap."""
from __future__ import annotations

import random
import time

from archmap.core.analyzer.impact_analyzer import (
    IMPACT_LIST_CAP,
    calculate_all_impacts,
    calculate_impact,
)


def _edge(source: str, target: str) -> dict:
    return {"source": source, "target": target}


def random_graph(seed: int) -> tuple[list[str], list[dict]]:
    """1-60 file nodes plus a few package nodes, random edges (cycles likely)."""
    rng = random.Random(seed)
    n_files = rng.randint(1, 60)
    files = [f"src/mod_{i:02d}.py" for i in range(n_files)]
    packages = [f"pkg:lib{i}" for i in range(rng.randint(0, 4))]
    ids = files + packages
    edges: list[dict] = []
    for _ in range(rng.randint(0, n_files * 3)):
        source = rng.choice(files)
        target = rng.choice(ids)
        if source != target:
            edges.append(_edge(source, target))
    rng.shuffle(ids)
    return ids, edges


def star(n: int) -> tuple[list[str], list[dict]]:
    """``hub`` plus ``n`` files that each import it."""
    leaves = [f"leaf_{i:04d}.py" for i in range(n)]
    return ["hub", *leaves], [_edge(leaf, "hub") for leaf in leaves]


def test_matches_bfs_on_random_graphs() -> None:
    for seed in range(30):
        ids, edges = random_graph(seed)
        fast = calculate_all_impacts(ids, edges, list_cap=10_000)
        assert set(fast) == set(ids)
        for n in ids:
            assert fast[n] == calculate_impact(n, edges), (seed, n)


def test_result_key_order_matches_calculate_impact() -> None:
    ids, edges = star(3)
    assert list(calculate_all_impacts(ids, edges)["hub"]) == list(calculate_impact("hub", edges))


def test_default_cap_is_200() -> None:
    assert IMPACT_LIST_CAP == 200


def test_cap_boundary() -> None:
    assert "impactedFilesTruncated" not in calculate_all_impacts(*star(200))["hub"]
    r = calculate_all_impacts(*star(201))["hub"]
    assert r["impactCount"] == 201
    assert len(r["impactedFiles"]) == 200
    assert r["impactedFilesTruncated"] is True
    assert r["impactedFiles"] == sorted(r["impactedFiles"])
    assert r["impactedFiles"] == calculate_impact("hub", star(201)[1])["impactedFiles"][:200]


def test_cap_excludes_self_inside_a_cycle() -> None:
    # Ring of 5 files: each impacts the other 4; cap 2 must never list itself.
    ring = [f"r{i}" for i in range(5)]
    edges = [_edge(ring[i], ring[(i + 1) % 5]) for i in range(5)]
    result = calculate_all_impacts(ring, edges, list_cap=2)
    for n in ring:
        assert result[n]["impactCount"] == 4
        assert n not in result[n]["impactedFiles"]
        assert result[n]["impactedFiles"] == sorted(set(ring) - {n})[:2]
        assert result[n]["impactedFilesTruncated"] is True


def test_package_node_capped() -> None:
    files = [f"app/f_{i:03d}.py" for i in range(250)]
    ids = ["pkg:redis", *files]
    edges = [_edge(f, "pkg:redis") for f in files]
    r = calculate_all_impacts(ids, edges)["pkg:redis"]
    assert r["impactCount"] == 250
    assert len(r["impactedFiles"]) == 200
    assert r["impactedFilesTruncated"] is True
    assert r["risk"] == "critical"


def test_should_stop_skips_lists_but_keeps_counts() -> None:
    ids, edges = star(5)
    r = calculate_all_impacts(ids, edges, should_stop=lambda: True)["hub"]
    assert r["impactCount"] == 5
    assert r["impactedFiles"] == []
    assert r["impactedFilesTruncated"] is True
    assert r["risk"] == "ok"


def test_worst_case_cycle_is_fast() -> None:
    # In-memory equivalent of the synthetic ``cycle`` shape: every node depends
    # on its 5 wrap-around neighbours, so the whole graph is one SCC.
    n = 5000
    ids = [f"module_{i:05d}.py" for i in range(n)]
    edges = [_edge(ids[i], ids[(i + j) % n]) for i in range(n) for j in range(1, 6)]
    start = time.perf_counter()
    result = calculate_all_impacts(ids, edges)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 3000, elapsed_ms
    assert all(result[node]["impactCount"] == n - 1 for node in ids)
    assert all(len(result[node]["impactedFiles"]) == IMPACT_LIST_CAP for node in ids)
