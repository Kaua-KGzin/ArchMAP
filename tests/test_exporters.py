from __future__ import annotations

import json

from archmap.exporters.cytoscape_exporter import export_graph_as_cytoscape
from archmap.exporters.json_exporter import export_graph_as_json
from archmap.exporters.mermaid_exporter import export_graph_as_mermaid


def test_exporters_create_json_mermaid_and_cytoscape_files(tmp_path) -> None:
    report = {
        "projectRoot": "/repo",
        "nodes": [
            {
                "id": "src/server.py",
                "label": "src/server.py",
                "type": "file",
                "outgoing": 1,
                "incoming": 0,
                "complexityImports": 1,
                "complexityScore": 1.0,
            },
            {
                "id": "pkg:requests",
                "label": "requests",
                "type": "package",
                "outgoing": 0,
                "incoming": 1,
                "complexityImports": 0,
                "complexityScore": 0.0,
            },
        ],
        "edges": [
            {
                "id": "src/server.py->pkg:requests",
                "source": "src/server.py",
                "target": "pkg:requests",
                "isCircular": False,
            }
        ],
        "metrics": {
            "filesAnalyzed": 1,
            "totalDependencies": 1,
            "externalDependencies": 1,
            "circularDependencyCount": 0,
            "complexity": [{"file": "src/server.py", "imports": 1, "score": 1.0}],
            "criticalFiles": [{"file": "src/server.py", "dependents": 0}],
        },
        "cycles": [],
        "risks": {"top_risk_files": []},
        "simple": {
            "nodes": ["src/server.py", "pkg:requests"],
            "edges": [["src/server.py", "pkg:requests"]],
        },
    }

    json_path = export_graph_as_json(report, tmp_path / "graph.json")
    mermaid_path = export_graph_as_mermaid(report, tmp_path / "graph.mmd")
    cytoscape_path = export_graph_as_cytoscape(report, tmp_path / "graph-cytoscape.json")

    json_content = json_path.read_text(encoding="utf-8")
    mermaid_content = mermaid_path.read_text(encoding="utf-8")
    cytoscape_payload = json.loads(cytoscape_path.read_text(encoding="utf-8"))

    assert '"nodes"' in json_content
    assert "graph TD" in mermaid_content
    assert "pkg_requests" in mermaid_content
    assert "file_src_server_py --> pkg_requests" in mermaid_content
    assert "nodes" in cytoscape_payload
    assert "edges" in cytoscape_payload
