from __future__ import annotations

from archmap.utils.file_utils import first_segment


def build_graph(parsed_project: dict) -> dict:
    node_map: dict[str, dict] = {}
    edge_map: dict[str, dict] = {}

    for file_entry in parsed_project["parsedFiles"]:
        node_map[file_entry["id"]] = {
            "id": file_entry["id"],
            "label": file_entry["label"],
            "type": "file",
            "language": file_entry["language"],
            "folder": first_segment(file_entry["id"]),
            "outgoing": 0,
            "incoming": 0,
            "isCircular": False,
        }

    for file_entry in parsed_project["parsedFiles"]:
        source_id = file_entry["id"]
        for dependency in file_entry["dependencies"]:
            dependency_id = dependency["id"]
            if dependency_id not in node_map:
                dependency_type = dependency.get("type", "package")
                node_map[dependency_id] = {
                    "id": dependency_id,
                    "label": dependency["label"],
                    "type": dependency_type,
                    "language": "unknown" if dependency_type == "file" else "package",
                    "folder": first_segment(dependency_id)
                    if dependency_type == "file"
                    else "(external)",
                    "outgoing": 0,
                    "incoming": 0,
                    "isCircular": False,
                }

            edge_id = f"{source_id}->{dependency_id}"
            if edge_id not in edge_map:
                edge_map[edge_id] = {
                    "id": edge_id,
                    "source": source_id,
                    "target": dependency_id,
                    "isCircular": False,
                }

    nodes = sorted(node_map.values(), key=_compare_nodes)
    edges = sorted(edge_map.values(), key=lambda item: item["id"])

    for edge in edges:
        source_node = node_map.get(edge["source"])
        target_node = node_map.get(edge["target"])
        if source_node:
            source_node["outgoing"] += 1
        if target_node:
            target_node["incoming"] += 1

    return {
        "projectRoot": parsed_project["projectRoot"],
        "nodes": nodes,
        "edges": edges,
    }


def _compare_nodes(node: dict) -> tuple[int, str]:
    return (0 if node.get("type") == "file" else 1, node["id"])
