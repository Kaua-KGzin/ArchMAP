from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from archmap.utils.file_utils import ensure_parent_dir
from archmap.utils.layers import build_layer_order, detect_layer


def export_graph_as_mermaid(
    report: dict, output_path: str | Path, no_subgraphs: bool = False
) -> Path:
    output_file = Path(output_path).resolve()
    ensure_parent_dir(output_file)

    lines = ["graph TD"]
    seen_node_ids: set[str] = set()

    if no_subgraphs:
        for node in report["nodes"]:
            _add_mermaid_node(node, lines, seen_node_ids)
    else:
        # Group by layer
        layer_order = build_layer_order(report.get("architecture", {}).get("activeLayerOrder"))
        layer_to_nodes: dict[str, list[dict]] = defaultdict(list)
        other_nodes = []

        for node in report["nodes"]:
            layer = detect_layer(node["id"], layer_order)
            if layer:
                layer_to_nodes[layer].append(node)
            else:
                other_nodes.append(node)

        # Sort layers by rank (high rank = top position in TD graph)
        # Higher rank (e.g. CLI=5) should come first in TD layout for top-down
        sorted_layers = sorted(
            layer_to_nodes.keys(),
            key=lambda layer_name: layer_order.get(layer_name, 0),
            reverse=True,
        )

        for layer in sorted_layers:
            safe_layer_id = layer.upper().replace("-", "_")
            lines.append(f"  subgraph {safe_layer_id}[{layer.upper()}]")
            for node in layer_to_nodes[layer]:
                _add_mermaid_node(node, lines, seen_node_ids, indent="    ")
            lines.append("  end")

        if other_nodes:
            lines.append("  subgraph OTHER[OTHER]")
            for node in other_nodes:
                _add_mermaid_node(node, lines, seen_node_ids, indent="    ")
            lines.append("  end")

    # Add edges
    for edge in report["edges"]:
        source = _to_mermaid_node_id(edge["source"], _infer_node_type(edge["source"]))
        target = _to_mermaid_node_id(edge["target"], _infer_node_type(edge["target"]))
        lines.append(f"  {source} --> {target}")

    lines.append("")
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def _add_mermaid_node(
    node: dict,
    lines: list[str],
    seen_ids: set[str],
    indent: str = "  ",
) -> None:
    node_id = _to_mermaid_node_id(node["id"], node["type"])
    if node_id in seen_ids:
        return
    seen_ids.add(node_id)
    label = _to_mermaid_label(node["label"])
    lines.append(f"{indent}{node_id}[{label}]")


def _to_mermaid_node_id(node_id: str, node_type: str) -> str:
    prefix = "pkg_" if node_type == "package" else "file_"
    stable = node_id.removeprefix("pkg:")
    sanitized = "".join(char if char.isalnum() or char == "_" else "_" for char in stable)
    return f"{prefix}{sanitized}"


def _infer_node_type(node_id: str) -> str:
    return "package" if node_id.startswith("pkg:") else "file"


def _to_mermaid_label(label: str) -> str:
    # Wrap in quotes at the call site is implicit; escape characters that would
    # otherwise break Mermaid node syntax. Backslash must be escaped first so we
    # do not double-escape the sequences introduced below.
    escaped = str(label).replace("\\", "\\\\")
    escaped = escaped.replace('"', "&quot;")
    escaped = escaped.replace("\n", " ").replace("\r", " ")
    escaped = escaped.replace("[", "(").replace("]", ")")
    escaped = escaped.replace("{", "(").replace("}", ")")
    escaped = escaped.replace("<", "&lt;").replace(">", "&gt;")
    return f'"{escaped}"'
