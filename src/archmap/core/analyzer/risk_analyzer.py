from __future__ import annotations

from collections import defaultdict

from archmap.utils.file_utils import first_segment, percentile

LAYER_ORDER = {
    "cli": 5,
    "web-ui": 5,
    "api": 5,
    "interface": 5,
    "app": 4,
    "application": 4,
    "core": 3,
    "domain": 3,
    "exporters": 2,
    "adapters": 2,
    "infra": 2,
    "utils": 1,
    "shared": 1,
}


def detect_architectural_risks(
    nodes: list[dict], edges: list[dict], cycles: list[list[str]]
) -> dict:
    file_nodes = [node for node in nodes if node.get("type") == "file"]
    file_ids = {node["id"] for node in file_nodes}

    outgoing_values = [int(node.get("outgoing", 0)) for node in file_nodes]
    total_connections = [
        int(node.get("outgoing", 0)) + int(node.get("incoming", 0)) for node in file_nodes
    ]

    god_threshold = max(8, percentile(outgoing_values, 0.9))
    explosion_threshold = max(12, percentile(total_connections, 0.9))

    god_modules = [
        {"file": node["id"], "outgoing": int(node.get("outgoing", 0))}
        for node in file_nodes
        if int(node.get("outgoing", 0)) >= god_threshold
    ]

    dependency_explosions = [
        {
            "file": node["id"],
            "incoming": int(node.get("incoming", 0)),
            "outgoing": int(node.get("outgoing", 0)),
            "totalConnections": int(node.get("incoming", 0)) + int(node.get("outgoing", 0)),
        }
        for node in file_nodes
        if int(node.get("incoming", 0)) + int(node.get("outgoing", 0)) >= explosion_threshold
    ]

    layer_violations: list[dict] = []
    violations_by_file: dict[str, int] = defaultdict(int)
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in file_ids or target not in file_ids:
            continue

        source_layer = first_segment(source)
        target_layer = first_segment(target)
        source_rank = LAYER_ORDER.get(source_layer)
        target_rank = LAYER_ORDER.get(target_layer)
        if source_rank is None or target_rank is None:
            continue
        if source_layer == target_layer:
            continue

        if source_rank < target_rank:
            layer_violations.append(
                {
                    "source": source,
                    "target": target,
                    "sourceLayer": source_layer,
                    "targetLayer": target_layer,
                    "rule": "lower-level module should not depend on higher-level module",
                }
            )
            violations_by_file[source] += 1

    cycle_members = {node_id for cycle in cycles for node_id in cycle}
    god_map = {item["file"] for item in god_modules}
    explosion_map = {item["file"] for item in dependency_explosions}

    top_risk_files: list[dict] = []
    for node in file_nodes:
        file_id = node["id"]
        incoming = int(node.get("incoming", 0))
        outgoing = int(node.get("outgoing", 0))

        score = incoming * 2 + outgoing
        signals: list[str] = []

        if file_id in cycle_members:
            score += 10
            signals.append("circular_dependency")
        if file_id in god_map:
            score += 8
            signals.append("god_module")
        if file_id in explosion_map:
            score += 6
            signals.append("dependency_explosion")
        if violations_by_file[file_id] > 0:
            score += violations_by_file[file_id] * 4
            signals.append(f"layer_violations:{violations_by_file[file_id]}")

        if score <= 0:
            continue

        top_risk_files.append(
            {
                "file": file_id,
                "riskScore": score,
                "dependents": incoming,
                "outgoing": outgoing,
                "signals": signals,
            }
        )

    top_risk_files.sort(key=lambda item: (-item["riskScore"], item["file"]))

    return {
        "god_modules": sorted(god_modules, key=lambda item: (-item["outgoing"], item["file"])),
        "layer_violations": layer_violations,
        "dependency_explosions": sorted(
            dependency_explosions,
            key=lambda item: (-item["totalConnections"], item["file"]),
        ),
        "top_risk_files": top_risk_files[:15],
        "thresholds": {
            "god_module_min_outgoing": god_threshold,
            "dependency_explosion_min_connections": explosion_threshold,
        },
    }
