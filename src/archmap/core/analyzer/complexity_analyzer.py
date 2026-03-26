from __future__ import annotations


def annotate_nodes_with_complexity(
    nodes: list[dict], cycle_membership: dict[str, int]
) -> list[dict]:
    file_nodes = [node for node in nodes if node.get("type") == "file"]
    max_outgoing = max((node.get("outgoing", 0) for node in file_nodes), default=0)
    max_incoming = max((node.get("incoming", 0) for node in file_nodes), default=0)
    max_connections = max(
        (int(node.get("outgoing", 0)) + int(node.get("incoming", 0)) for node in file_nodes),
        default=0,
    )
    annotated: list[dict] = []

    for node in nodes:
        is_circular = node.get("id") in cycle_membership
        if node.get("type") != "file":
            annotated.append(
                {
                    **node,
                    "isCircular": is_circular,
                    "complexityImports": 0,
                    "complexityDependents": 0,
                    "complexityConnections": 0,
                    "complexityScore": 0.0,
                }
            )
            continue

        outgoing = int(node.get("outgoing", 0))
        incoming = int(node.get("incoming", 0))
        total_connections = outgoing + incoming
        complexity_score = _complexity_score(
            outgoing,
            incoming,
            total_connections,
            max_outgoing,
            max_incoming,
            max_connections,
        )
        instability = _instability(outgoing, incoming)
        annotated.append(
            {
                **node,
                "isCircular": is_circular,
                "complexityImports": outgoing,
                "complexityDependents": incoming,
                "complexityConnections": total_connections,
                "complexityScore": complexity_score,
                "efferentCoupling": outgoing,
                "afferentCoupling": incoming,
                "instability": instability,
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
                "dependents": node.get("incoming", 0),
                "totalConnections": node.get("complexityConnections", 0),
                "efferentCoupling": node.get("efferentCoupling", node.get("outgoing", 0)),
                "afferentCoupling": node.get("afferentCoupling", node.get("incoming", 0)),
                "instability": node.get("instability", 0.0),
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


def summarize_coupling(nodes: list[dict]) -> dict:
    file_nodes = [node for node in nodes if node.get("type") == "file"]
    if not file_nodes:
        return {
            "averageInstability": 0.0,
            "mostStable": [],
            "mostVolatile": [],
        }

    average_instability = round(
        sum(float(node.get("instability", 0.0)) for node in file_nodes) / len(file_nodes),
        6,
    )
    most_stable = sorted(
        (
            {
                "file": node["id"],
                "afferentCoupling": node.get("afferentCoupling", 0),
                "efferentCoupling": node.get("efferentCoupling", 0),
                "instability": node.get("instability", 0.0),
            }
            for node in file_nodes
            if int(node.get("afferentCoupling", 0)) > 0 or int(node.get("efferentCoupling", 0)) > 0
        ),
        key=lambda item: (item["instability"], -item["afferentCoupling"], item["file"]),
    )[:5]
    most_volatile = sorted(
        (
            {
                "file": node["id"],
                "afferentCoupling": node.get("afferentCoupling", 0),
                "efferentCoupling": node.get("efferentCoupling", 0),
                "instability": node.get("instability", 0.0),
            }
            for node in file_nodes
            if int(node.get("afferentCoupling", 0)) > 0 or int(node.get("efferentCoupling", 0)) > 0
        ),
        key=lambda item: (-item["instability"], -item["efferentCoupling"], item["file"]),
    )[:5]

    return {
        "averageInstability": average_instability,
        "mostStable": most_stable,
        "mostVolatile": most_volatile,
    }


def _complexity_score(
    outgoing_imports: int,
    incoming_dependents: int,
    total_connections: int,
    max_outgoing_imports: int,
    max_incoming_dependents: int,
    max_connections: int,
) -> float:
    if max_outgoing_imports <= 0 and max_incoming_dependents <= 0 and max_connections <= 0:
        return 0.0

    outgoing_score = _normalized_ratio(outgoing_imports, max_outgoing_imports)
    incoming_score = _normalized_ratio(incoming_dependents, max_incoming_dependents)
    connection_score = _normalized_ratio(total_connections, max_connections)
    return round((outgoing_score + incoming_score + connection_score) / 3, 6)


def _normalized_ratio(value: int, maximum: int) -> float:
    if maximum <= 0:
        return 0.0
    return value / maximum


def _instability(outgoing_imports: int, incoming_dependents: int) -> float:
    total = outgoing_imports + incoming_dependents
    if total <= 0:
        return 0.0
    return round(outgoing_imports / total, 6)
