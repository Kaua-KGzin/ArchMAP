from __future__ import annotations

from collections import deque
from collections.abc import Callable
from itertools import compress, islice

from archmap.types import ImpactResult

#: Maximum number of entries materialised in ``impactedFiles`` per node by
#: :func:`calculate_all_impacts`.  ``impactCount`` is always exact.
IMPACT_LIST_CAP: int = 200

_BIT_WINDOW = 4096
_SPARSE_RATIO = 32  # windows with < 1/32 bits set are scanned with str.find
_BIT_FLAGS = bytes.maketrans(b"01", b"\x00\x01")


def build_dependents_map(edges: list[dict]) -> dict[str, list[str]]:
    """Build a backward adjacency map (target -> sources that depend on it).

    Computing this once and reusing it across every node turns whole-graph
    impact analysis from O(V * E) into O(V + E).  If ``source`` depends on
    ``target``, then ``target`` impacts ``source``.
    """
    dependents_map: dict[str, list[str]] = {}
    for edge in edges:
        dependents_map.setdefault(edge["target"], []).append(edge["source"])
    return dependents_map


def calculate_impact(
    node_id: str,
    edges: list[dict],
    dependents_map: dict[str, list[str]] | None = None,
) -> dict:
    """Return the transitive set of files impacted by a change to ``node_id``.

    ``dependents_map`` may be supplied (via :func:`build_dependents_map`) to
    avoid rebuilding the backward adjacency on every call; when omitted it is
    derived from ``edges`` for backward compatibility.
    """
    if dependents_map is None:
        dependents_map = build_dependents_map(edges)

    impacted: set[str] = set()
    visited = {node_id}
    queue: deque[str] = deque([node_id])

    while queue:
        current = queue.popleft()
        for dependent in dependents_map.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                impacted.add(dependent)
                queue.append(dependent)

    count = len(impacted)
    return {
        "nodeId": node_id,
        "impactedFiles": sorted(impacted),
        "impactCount": count,
        "risk": _risk_for(count),
    }


def full_impacted_files(report: dict, node_id: str) -> list[str]:
    """Complete, sorted ``impactedFiles`` for ``node_id`` of an analysis report.

    The stored list is capped at :data:`IMPACT_LIST_CAP`; when the node's
    impact is flagged ``impactedFilesTruncated`` the full list is recomputed
    with a single BFS over ``report["edges"]``.
    """
    node = next((n for n in report.get("nodes", []) if n.get("id") == node_id), None)
    impact = (node or {}).get("impact") or {}
    if not impact.get("impactedFilesTruncated"):
        return list(impact.get("impactedFiles", []))
    return list(calculate_impact(node_id, report.get("edges", []))["impactedFiles"])


def _risk_for(count: int) -> str:
    if count > 10:
        return "critical"
    if count > 5:
        return "warning"
    if count > 0:
        return "ok"
    return "low"


def calculate_all_impacts(
    node_ids: list[str],
    edges: list[dict],
    *,
    list_cap: int = IMPACT_LIST_CAP,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, ImpactResult]:
    """Impact of every node in ``node_ids``, computed on the SCC condensation.

    Equivalent to calling :func:`calculate_impact` per node, except that
    ``impactedFiles`` holds at most ``list_cap`` entries (the first ones in
    sorted order); when entries were left out the result also carries
    ``impactedFilesTruncated: True``.  ``impactCount`` is always exact.

    The reverse graph (target -> dependents) is condensed into strongly
    connected components with an iterative Tarjan, whose emission order is
    already reverse topological: every component a component reaches has been
    emitted before it.  Each component's reach set is an ``int`` bitset (bit
    position = rank of the node id in sorted order, so the lowest set bits are
    the alphabetically first impacted nodes) built as the union of its own
    members and its successors' reach sets.  A reach set is dropped as soon as
    every component that depends on it has consumed it.

    ``should_stop`` is polled once per component; after it returns ``True``
    the remaining nodes get an empty (truncated) list but exact counts.
    """
    # Every edge endpoint takes part in the traversal, as in calculate_impact().
    universe = set(node_ids)
    for edge in edges:
        universe.add(edge["source"])
        universe.add(edge["target"])
    names = sorted(universe)
    index = {name: i for i, name in enumerate(names)}

    successors: list[list[int]] = [[] for _ in names]
    for edge in edges:
        successors[index[edge["target"]]].append(index[edge["source"]])

    components, comp_of = _tarjan_scc(successors)

    # Distinct successor components per component, and how many components
    # still have to consume each reach set before it can be dropped.
    comp_succ: list[list[int]] = []
    pending = [0] * len(components)
    for cid, members in enumerate(components):
        targets = {comp_of[s] for m in members for s in successors[m]}
        targets.discard(cid)
        comp_succ.append(list(targets))
        for t in targets:
            pending[t] += 1

    wanted = {index[name] for name in node_ids}
    results_by_index: dict[int, ImpactResult] = {}
    reach: dict[int, int] = {}
    cap = max(0, list_cap)
    stopped = False

    for cid, members in enumerate(components):
        if not stopped and should_stop is not None and should_stop():
            stopped = True
        bits = 0
        for m in members:
            bits |= 1 << m
        for t in comp_succ[cid]:
            bits |= reach[t]
            pending[t] -= 1
            if pending[t] == 0:
                del reach[t]
        if pending[cid]:
            reach[cid] = bits

        outputs = [m for m in members if m in wanted]
        if not outputs:
            continue
        count = bits.bit_count() - 1
        effective_cap = 0 if stopped else cap
        # One extra entry so a member can drop itself and still fill the cap.
        prefix = _lowest_set_bits(bits, effective_cap + 1) if effective_cap else []
        prefix_names = list(map(names.__getitem__, prefix))
        prefix_set = set(prefix)
        for m in outputs:
            if m in prefix_set:
                listed = [names[i] for i in prefix if i != m][:effective_cap]
            else:
                listed = prefix_names[:effective_cap]
            result: ImpactResult = {
                "nodeId": names[m],
                "impactedFiles": listed,
                "impactCount": count,
                "risk": _risk_for(count),
            }
            if len(listed) < count:
                result["impactedFilesTruncated"] = True
            results_by_index[m] = result

    return {name: results_by_index[index[name]] for name in node_ids}


def _lowest_set_bits(bits: int, limit: int) -> list[int]:
    """Positions of the ``limit`` lowest set bits of ``bits``, ascending.

    Scans fixed-width windows starting at the lowest set bit; each window is
    turned into a 0/1 flag string and the positions are picked out with
    ``itertools.compress``, so the per-bit work happens in C rather than in a
    Python loop (a 50k-node chain extracts ~10M positions).
    """
    found: list[int] = []
    if limit <= 0 or bits == 0:
        return found
    end = bits.bit_length()
    pos = (bits & -bits).bit_length() - 1
    width = _BIT_WINDOW
    mask = (1 << width) - 1
    while pos < end and len(found) < limit:
        window = (bits >> pos) & mask
        if window:
            text = format(window, f"0{width}b")[::-1]
            if window.bit_count() * _SPARSE_RATIO < width:
                # Sparse: str.find skips runs of zeros at C speed.
                at = text.find("1")
                while at != -1 and len(found) < limit:
                    found.append(pos + at)
                    at = text.find("1", at + 1)
            else:
                flags = text.encode("ascii").translate(_BIT_FLAGS)
                found.extend(islice(compress(range(pos, pos + width), flags), limit - len(found)))
        pos += width
    return found


def _tarjan_scc(successors: list[list[int]]) -> tuple[list[list[int]], list[int]]:
    """Iterative Tarjan strongly connected components (no recursion).

    Returns the components in emission order (reverse topological: a
    component is emitted after every component reachable from it) and the
    component id of each vertex.
    """
    size = len(successors)
    unvisited = -1
    order = [unvisited] * size
    low = [0] * size
    on_stack = [False] * size
    comp_of = [unvisited] * size
    stack: list[int] = []
    components: list[list[int]] = []
    counter = 0

    for root in range(size):
        if order[root] != unvisited:
            continue
        order[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        work: list[tuple[int, int]] = [(root, 0)]
        while work:
            v, i = work[-1]
            succ = successors[v]
            if i < len(succ):
                work[-1] = (v, i + 1)
                w = succ[i]
                if order[w] == unvisited:
                    order[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    work.append((w, 0))
                elif on_stack[w] and order[w] < low[v]:
                    low[v] = order[w]
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                if low[v] < low[parent]:
                    low[parent] = low[v]
            if low[v] == order[v]:
                cid = len(components)
                members: list[int] = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp_of[w] = cid
                    members.append(w)
                    if w == v:
                        break
                components.append(members)
    return components, comp_of
