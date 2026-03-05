from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from archmap.utils.file_utils import ensure_parent_dir


def export_graph_as_json(report: dict, output_path: str | Path) -> Path:
    target = Path(output_path).resolve()
    ensure_parent_dir(target)

    payload = {
        "projectRoot": report["projectRoot"],
        "generatedAt": datetime.now(UTC).isoformat(),
        "nodes": report["simple"]["nodes"],
        "edges": report["simple"]["edges"],
        "metrics": report["metrics"],
        "cycles": report["cycles"],
        "risks": report.get("risks", {}),
        "detailed": {
            "nodes": report["nodes"],
            "edges": report["edges"],
        },
    }

    target.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    return target
