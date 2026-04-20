from __future__ import annotations

import json

from archmap.exporters.sarif_exporter import export_graph_as_sarif


def _base_report(project_root: str = "/repo") -> dict:
    return {
        "projectRoot": project_root,
        "metrics": {"filesAnalyzed": 2},
        "cycles": [],
        "cycleDetails": [],
        "risks": {
            "layer_violations": [],
            "god_modules": [],
            "dependency_explosions": [],
        },
        "architecture": {"ruleViolations": [], "health": {"score": 90}},
    }


def test_sarif_empty_project_is_valid_sarif(tmp_path):
    report = _base_report()
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["version"] == "2.1.0"
    assert "$schema" in data
    assert len(data["runs"]) == 1
    assert data["runs"][0]["results"] == []


def test_sarif_tool_info(tmp_path):
    from archmap import __version__

    report = _base_report()
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    driver = data["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ArchMAP"
    assert driver["version"] == __version__
    assert len(driver["rules"]) == 5


def test_sarif_rules_have_required_fields(tmp_path):
    report = _base_report()
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    for rule in data["runs"][0]["tool"]["driver"]["rules"]:
        assert "id" in rule
        assert "name" in rule
        assert "shortDescription" in rule
        assert "defaultConfiguration" in rule


def test_sarif_circular_dependency_generates_arch001(tmp_path):
    report = _base_report()
    report["cycles"] = [["src/a.py", "src/b.py"]]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    results = data["runs"][0]["results"]
    arch001 = [r for r in results if r["ruleId"] == "ARCH001"]
    # Two files in the cycle → two results
    assert len(arch001) == 2
    assert all(r["level"] == "warning" for r in arch001)
    # Message mentions cycle path
    assert "src/a.py" in arch001[0]["message"]["text"]


def test_sarif_self_cycle_single_result(tmp_path):
    report = _base_report()
    report["cycles"] = [["src/self.py"]]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    arch001 = [r for r in data["runs"][0]["results"] if r["ruleId"] == "ARCH001"]
    assert len(arch001) == 1


def test_sarif_layer_violation_generates_arch002(tmp_path):
    report = _base_report()
    report["risks"]["layer_violations"] = [
        {"from": "src/core/a.py", "to": "src/cli/b.py", "rule": "core -> cli"}
    ]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    arch002 = [r for r in data["runs"][0]["results"] if r["ruleId"] == "ARCH002"]
    assert len(arch002) == 1
    assert arch002[0]["level"] == "error"
    assert "core" in arch002[0]["message"]["text"]


def test_sarif_god_module_generates_arch003(tmp_path):
    report = _base_report()
    report["risks"]["god_modules"] = [{"file": "src/mega.py", "outgoing": 40}]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    arch003 = [r for r in data["runs"][0]["results"] if r["ruleId"] == "ARCH003"]
    assert len(arch003) == 1
    assert arch003[0]["level"] == "note"


def test_sarif_dependency_explosion_generates_arch004(tmp_path):
    report = _base_report()
    report["risks"]["dependency_explosions"] = [{"file": "src/bloated.py", "outgoing": 25}]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    arch004 = [r for r in data["runs"][0]["results"] if r["ruleId"] == "ARCH004"]
    assert len(arch004) == 1


def test_sarif_custom_rule_violation_generates_arch005(tmp_path):
    report = _base_report()
    report["architecture"]["ruleViolations"] = [
        {"from": "src/parser.py", "to": "src/cli/main.py", "rule": "parser -> cli"}
    ]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    arch005 = [r for r in data["runs"][0]["results"] if r["ruleId"] == "ARCH005"]
    assert len(arch005) == 1
    assert arch005[0]["level"] == "error"


def test_sarif_location_references_file(tmp_path):
    report = _base_report()
    report["cycles"] = [["src/utils/helper.py", "src/core/engine.py"]]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    results = data["runs"][0]["results"]
    uris = [
        r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for r in results
        if r.get("locations")
    ]
    assert "src/utils/helper.py" in uris or "src/core/engine.py" in uris


def test_sarif_combined_issues(tmp_path):
    report = _base_report()
    report["cycles"] = [["a.py", "b.py"]]
    report["risks"]["god_modules"] = [{"file": "big.py", "outgoing": 50}]
    report["risks"]["layer_violations"] = [
        {"from": "core.py", "to": "cli.py", "rule": "core -> cli"}
    ]
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    results = data["runs"][0]["results"]
    rule_ids = {r["ruleId"] for r in results}
    assert "ARCH001" in rule_ids
    assert "ARCH002" in rule_ids
    assert "ARCH003" in rule_ids


def test_sarif_file_is_created_at_output_path(tmp_path):
    report = _base_report()
    nested = tmp_path / "deep" / "nested" / "results.sarif"
    path = export_graph_as_sarif(report, nested)
    assert path.exists()
    assert path == nested


def test_sarif_metadata_in_run_properties(tmp_path):
    report = _base_report()
    report["metrics"]["filesAnalyzed"] = 42
    path = export_graph_as_sarif(report, tmp_path / "results.sarif")
    data = json.loads(path.read_text(encoding="utf-8"))

    props = data["runs"][0]["properties"]
    assert props["filesAnalyzed"] == 42
    assert "generatedAt" in props
