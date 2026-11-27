"""Betweenness centrality of the file dependency graph.

A file with high betweenness sits on many of the shortest import chains
between other files: changes and failures funnel through it even when its
own incoming/outgoing counts look ordinary. That is the structural
bottleneck that fan-in/fan-out (and therefore ``riskScore``) can miss.

Brandes' algorithm on the directed, unweighted file graph (``A -> B`` means
``A`` imports ``B``). Scores are normalised by the number of ordered file
pairs that are connected by an import chain at all, not by ``(n-1)(n-2)``:
dependency graphs are sparse, most pairs have no path, and the textbook
normalisation would make every score look negligible. A score of ``0.3``
therefore reads directly as "on 30% of the shortest import chains".

Above ``exact_limit`` files both sums run over the same deterministic sample
of source files (Brandes & Pich, 2007), so the ratio needs no rescaling and
large repositories stay well under a second. The result is reported beside
the risk score, never folded into it.

With ``should_stop`` (the soft time budget) the source loop polls it every
``STOP_CHECK_EVERY`` sources and stops with what it has; the scores then come
from the sources processed so far (``stoppedEarly`` / ``sourcesProcessed``).
"""

from __future__ import annotations

import random
import statistics
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from archmap.core.analyzer.test_mapping import is_test_file
from archmap.types import Finding

EXACT_LIMIT = 1000
DEFAULT_SAMPLES = 256
STOP_CHECK_EVERY = 16
# A bottleneck lies on at least this share of the connected import chains...
MIN_BOTTLENECK_SCORE = 0.10
# ...in a graph with enough chains for a share to mean something.
MIN_CONNECTED_PAIRS = 50
MAX_CENTRALITY_FINDINGS = 5
TOP_N = 10


def betweenness_centrality(
    nodes: Iterable[str],
    edges: Iterable[tuple[str, str]],
    *,
    exact_limit: int = EXACT_LIMIT,
    samples: int = DEFAULT_SAMPLES,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Share of connected import chains through each node, plus how it was computed."""
    names = sorted(set(nodes))
    index = {name: i for i, name in enumerate(names)}
    n = len(names)
    adjacency: list[list[int]] = [[] for _ in range(n)]
    seen: set[tuple[int, int]] = set()
    for source, target in edges:
        a, b = index.get(source), index.get(target)
        if a is None or b is None or a == b or (a, b) in seen:
            continue
        seen.add((a, b))
        adjacency[a].append(b)

    if n <= exact_limit or samples >= n:
        sources: list[int] = list(range(n))
        meta: dict[str, Any] = {"method": "exact", "nodes": n}
    else:
        sources = sorted(random.Random(0).sample(range(n), samples))
        meta = {"method": "sampled", "samples": samples, "nodes": n}

    raw = [0.0] * n
    connected = 0
    processed = 0
    for s in sources:
        if should_stop is not None and processed % STOP_CHECK_EVERY == 0 and should_stop():
            meta["stoppedEarly"] = True
            meta["sourcesProcessed"] = processed
            break
        connected += _accumulate_from(s, adjacency, raw)
        processed += 1

    scale = 1.0 / connected if connected else 0.0
    sample_factor = n / processed if processed else 0.0
    meta["connectedPairs"] = round(connected * sample_factor)
    return {names[i]: raw[i] * scale for i in range(n)}, meta


def _accumulate_from(s: int, adjacency: list[list[int]], raw: list[float]) -> int:
    """One Brandes pass from ``s``; returns how many files ``s`` reaches."""
    n = len(adjacency)
    sigma = [0] * n
    dist = [-1] * n
    preds: list[list[int]] = [[] for _ in range(n)]
    sigma[s] = 1
    dist[s] = 0
    order: list[int] = []
    queue = deque([s])
    while queue:
        v = queue.popleft()
        order.append(v)
        next_dist = dist[v] + 1
        for w in adjacency[v]:
            if dist[w] < 0:
                dist[w] = next_dist
                queue.append(w)
            if dist[w] == next_dist:
                sigma[w] += sigma[v]
                preds[w].append(v)
    delta = [0.0] * n
    for w in reversed(order):
        coefficient = (1.0 + delta[w]) / sigma[w]
        for v in preds[w]:
            delta[v] += sigma[v] * coefficient
        if w != s:
            raw[w] += delta[w]
    return len(order) - 1


def summarize_centrality(scores: Mapping[str, float], meta: Mapping[str, Any]) -> dict[str, Any]:
    top = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    return {
        **meta,
        "top": [{"file": f, "betweenness": round(s, 4)} for f, s in top if s > 0],
    }


def build_centrality_findings(
    scores: Mapping[str, float], meta: Mapping[str, Any]
) -> list[Finding]:
    """``GRAPH-*`` findings for the few files most import chains pass through.

    Test files are skipped: a shared test fixture can sit on many chains,
    but it is not part of the architecture being reviewed.
    """
    if int(meta.get("connectedPairs", 0)) < MIN_CONNECTED_PAIRS:
        return []
    if meta.get("stoppedEarly"):
        # Scores from a prefix of the sources cut short by the time budget are
        # biased toward those sources: not a basis for a finding.
        return []
    sampled = meta.get("method") == "sampled"
    typical = statistics.median(scores.values()) if scores else 0.0
    ranked = sorted(
        (
            (f, s)
            for f, s in scores.items()
            if s >= MIN_BOTTLENECK_SCORE and not is_test_file(f)
        ),
        key=lambda kv: (-kv[1], kv[0]),
    )
    findings: list[Finding] = []
    for file_id, score in ranked[:MAX_CENTRALITY_FINDINGS]:
        share = f"{score * 100:.1f}%"
        findings.append(
            Finding(
                id=f"GRAPH-{len(findings) + 1:03d}",
                domain="code",
                category="structural_bottleneck",
                severity="medium" if score >= 0.25 else "low",
                confidence=0.8 if sampled else 0.9,
                message=(
                    f"Structural bottleneck: {file_id} lies on {share} of the shortest "
                    "import chains between other files"
                ),
                evidence=[
                    f"Betweenness: {score:.4f} (median file: {typical:.4f})",
                    f"Connected import chains in the graph: {meta.get('connectedPairs')}",
                    "Computed by sampling source files" if sampled else "Exact computation",
                ],
                file=file_id,
                remediation=(
                    "Changes here reach far through the graph. Consider splitting it by "
                    "responsibility or putting a narrow interface in front of it."
                ),
            )
        )
    return findings
