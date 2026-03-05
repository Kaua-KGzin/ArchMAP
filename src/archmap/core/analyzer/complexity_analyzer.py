from __future__ import annotations


def annotate_nodes_with_complexity(
    nodes: list[dict], cycle_membership: dict[str, int]
) -> list[dict]:
    file_nodes = [node for node in nodes if node.get("type") == "file"]
    max_outgoing = max((node.get("outgoing", 0) for node in file_nodes), default=0)
    annotated: list[dict] = []

    for node in nodes:
        is_circular = node.get("id") in cycle_membership
        if node.get("type") != "file":
            annotated.append(
                {
                    **node,
                    "isCircular": is_circular,
                    "complexityImports": 0,
                    "complexityScore": 0.0,
                }
            )
            continue

        outgoing = int(node.get("outgoing", 0))
        complexity_score = _complexity_score(outgoing, max_outgoing)
        annotated.append(
            {
                **node,
                "isCircular": is_circular,
                "complexityImports": outgoing,
                "complexityScore": complexity_score,
            }
        )

    return annotated


def summarize_complexity(nodes: list[dict]) -> list[dict]:
    summary = []
    for node in nodes:
        if node.get("type") != "file":
            continue
        summary.append(
            {
                "file": node["id"],
                "imports": node.get("outgoing", 0),
                "score": node.get("complexityScore", 0.0),
            }
        )
    return sorted(summary, key=lambda item: (-item["score"], item["file"]))


def summarize_critical_files(nodes: list[dict]) -> list[dict]:
    summary = []
    for node in nodes:
        if node.get("type") != "file":
            continue
        summary.append(
            {
                "file": node["id"],
                "dependents": node.get("incoming", 0),
            }
        )
    return sorted(summary, key=lambda item: (-item["dependents"], item["file"]))


def _complexity_score(outgoing_imports: int, max_outgoing_imports: int) -> float:
    if max_outgoing_imports <= 0:
        return 0.0
    return round(outgoing_imports / max_outgoing_imports, 6)
