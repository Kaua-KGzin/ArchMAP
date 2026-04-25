from __future__ import annotations

import json
from pathlib import Path

import pytest

from archmap.exporters.sarif_exporter import export_graph_as_sarif


def _minimal_report(project_root: str = "/tmp/project") -> dict:
    return {
        "projectRoot": project_root,
        "nodes": [],
        "edges": [],
        "simple": {"nodes": [], "edges": []},
        "metrics": {},
        "cycles": [],
        "risks": {},
        "architecture": {},
    }


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

def test_export_creates_file(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    out = tmp_path / "archmap.sarif"
    result = export_graph_as_sarif(report, out)
    assert result == out
    assert out.is_file()


def test_sarif_schema_and_version(tmp_path: Path) -> None:
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(_minimal_report(str(tmp_path)), out)
    sarif = json.loads(out.read_text())
    assert sarif["version"] == "2.1.0"
    assert "json.schemastore.org/sarif" in sarif["$schema"]


def test_sarif_tool_name(tmp_path: Path) -> None:
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(_minimal_report(str(tmp_path)), out)
    sarif = json.loads(out.read_text())
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ArchMAP"
    assert len(driver["rules"]) >= 4


def test_empty_report_produces_no_results(tmp_path: Path) -> None:
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(_minimal_report(str(tmp_path)), out)
    sarif = json.loads(out.read_text())
    assert sarif["runs"][0]["results"] == []


# ---------------------------------------------------------------------------
# Cycles
# ---------------------------------------------------------------------------

def test_cycle_produces_warning_result(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["cycles"] = [["src/a.py", "src/b.py", "src/c.py"]]
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    r = results[0]
    assert r["ruleId"] == "archmap/cycle"
    assert r["level"] == "warning"
    assert "src/a.py" in r["message"]["text"]
    assert r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/a.py"


def test_empty_cycle_is_skipped(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["cycles"] = [[]]
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    assert sarif["runs"][0]["results"] == []


# ---------------------------------------------------------------------------
# Rule violations
# ---------------------------------------------------------------------------

def test_rule_violation_produces_error_result(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["architecture"] = {
        "ruleViolations": [
            {
                "source": "src/ui/button.py",
                "target": "src/db/session.py",
                "kind": "forbid",
                "rule": "ui -> db",
                "message": "ui -> db is forbidden but src/ui/button.py depends on src/db/session.py",
            }
        ]
    }
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    r = results[0]
    assert r["ruleId"] == "archmap/rule-violation"
    assert r["level"] == "error"
    assert "src/ui/button.py" in r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]


# ---------------------------------------------------------------------------
# Risk files
# ---------------------------------------------------------------------------

def test_god_module_produces_high_risk_result(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["risks"] = {"god_modules": [{"id": "src/core.py"}]}
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    r = results[0]
    assert r["ruleId"] == "archmap/high-risk"
    assert "god module" in r["message"]["text"]


def test_dependency_explosion_produces_high_risk_result(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["risks"] = {"dependency_explosions": [{"id": "src/hub.py"}]}
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    r = sarif["runs"][0]["results"][0]
    assert r["ruleId"] == "archmap/high-risk"
    assert "dependency explosion" in r["message"]["text"]


def test_duplicate_risk_file_not_doubled(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["risks"] = {
        "god_modules": [{"id": "src/hub.py"}],
        "dependency_explosions": [{"id": "src/hub.py"}],
    }
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    assert len(sarif["runs"][0]["results"]) == 1


# ---------------------------------------------------------------------------
# Layer violations
# ---------------------------------------------------------------------------

def test_layer_violation_produces_warning_result(tmp_path: Path) -> None:
    report = _minimal_report(str(tmp_path))
    report["risks"] = {
        "layer_violations": [{"source": "src/db/repo.py", "target": "src/ui/form.py"}]
    }
    out = tmp_path / "out.sarif"
    export_graph_as_sarif(report, out)
    sarif = json.loads(out.read_text())
    r = sarif["runs"][0]["results"][0]
    assert r["ruleId"] == "archmap/layer-violation"
    assert r["level"] == "warning"
    assert "src/db/repo.py" in r["message"]["text"]


# ---------------------------------------------------------------------------
# Output path auto-creation
# ---------------------------------------------------------------------------

def test_export_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "subdir" / "nested" / "archmap.sarif"
    export_graph_as_sarif(_minimal_report(str(tmp_path)), out)
    assert out.is_file()
