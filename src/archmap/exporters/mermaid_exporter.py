from __future__ import annotations

from pathlib import Path

from archmap.utils.file_utils import ensure_parent_dir


def export_graph_as_mermaid(report: dict, output_path: str | Path) -> Path:
    output_file = Path(output_path).resolve()
    ensure_parent_dir(output_file)

    lines = ["graph TD"]
    seen_node_ids: set[str] = set()

    for node in report["nodes"]:
        node_id = _to_mermaid_node_id(node["id"], node["type"])
        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        lines.append(f"  {node_id}[{_to_mermaid_label(node['label'])}]")

    for edge in report["edges"]:
        source = _to_mermaid_node_id(edge["source"], _infer_node_type(edge["source"]))
        target_node = _to_mermaid_node_id(edge["target"], _infer_node_type(edge["target"]))
        lines.append(f"  {source} --> {target_node}")

    lines.append("")
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def _to_mermaid_node_id(node_id: str, node_type: str) -> str:
    prefix = "pkg_" if node_type == "package" else "file_"
    stable = node_id.removeprefix("pkg:")
    sanitized = "".join(char if char.isalnum() or char == "_" else "_" for char in stable)
    return f"{prefix}{sanitized}"


def _infer_node_type(node_id: str) -> str:
    return "package" if node_id.startswith("pkg:") else "file"


def _to_mermaid_label(label: str) -> str:
    return str(label).replace('"', '\\"')
