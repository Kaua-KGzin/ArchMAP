from __future__ import annotations

import json
from pathlib import Path

from archmap.utils.file_utils import ensure_parent_dir


def export_graph_as_cytoscape(report: dict, output_path: str | Path) -> Path:
    target = Path(output_path).resolve()
    ensure_parent_dir(target)

    elements = {
        "nodes": [{"data": node} for node in report["nodes"]],
        "edges": [{"data": edge} for edge in report["edges"]],
        "metadata": {
            "projectRoot": report["projectRoot"],
            "metrics": report["metrics"],
            "cycles": report["cycles"],
            "risks": report.get("risks", {}),
        },
    }

    target.write_text(f"{json.dumps(elements, indent=2)}\n", encoding="utf-8")
    return target
