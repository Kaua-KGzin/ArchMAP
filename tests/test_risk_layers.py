from __future__ import annotations

from archmap.core.analyzer.risk_analyzer import detect_architectural_risks


def test_layer_violations_detected_with_src_prefix_paths() -> None:
    nodes = [
        {"id": "src/core/service.py", "type": "file", "incoming": 0, "outgoing": 1},
        {"id": "src/cli/main.py", "type": "file", "incoming": 1, "outgoing": 0},
    ]
    edges = [{"source": "src/core/service.py", "target": "src/cli/main.py"}]

    risks = detect_architectural_risks(nodes, edges, cycles=[])

    assert len(risks["layer_violations"]) == 1
    violation = risks["layer_violations"][0]
    assert violation["sourceLayer"] == "core"
    assert violation["targetLayer"] == "cli"


def test_same_layer_dependency_is_not_a_violation() -> None:
    nodes = [
        {"id": "src/core/a.py", "type": "file", "incoming": 0, "outgoing": 1},
        {"id": "src/core/b.py", "type": "file", "incoming": 1, "outgoing": 0},
    ]
    edges = [{"source": "src/core/a.py", "target": "src/core/b.py"}]

    risks = detect_architectural_risks(nodes, edges, cycles=[])

    assert risks["layer_violations"] == []
