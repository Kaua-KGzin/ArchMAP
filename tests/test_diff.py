from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from archmap.core.analyzer.diff_analyzer import analyze_git_ref, diff_reports, normalize_report

NodeFactory = Callable[..., dict]
EdgeFactory = Callable[..., dict]


def test_diff_reports_detects_dependency_and_cycle_changes(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.email", "archmap@example.com")
    _git(repo, "config", "user.name", "ArchMAP Test")
    _git(repo, "config", "commit.gpgsign", "false")

    (repo / "a.py").write_text("from b import fn\n", encoding="utf-8")
    (repo / "b.py").write_text("def fn():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")

    (repo / "b.py").write_text("import a\n\ndef fn():\n    return 2\n", encoding="utf-8")
    (repo / "c.py").write_text("import a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head")

    base_report = analyze_git_ref(repo, "HEAD~1")
    base_report["ref"] = "HEAD~1"
    head_report = analyze_git_ref(repo, "HEAD")
    head_report["ref"] = "HEAD"

    diff = diff_reports(base_report, head_report)

    assert diff["edges"]["delta"] > 0
    assert diff["cycles"]["delta"] == 1
    assert "deltaPercent" in diff["complexity"]
    assert "healthDelta" in diff["architecture"]
    assert diff["files"]["delta"] == 1
    assert diff["files"]["added"] == ["c.py"]
    assert diff["files"]["removed"] == []
    assert diff["files"]["changed"]
    changed_b = next(item for item in diff["files"]["changed"] if item["file"] == "b.py")
    assert changed_b["addedDependencies"] == ["a.py"]


def test_diff_reports_uses_shared_graph_fixtures_for_file_deltas(
    make_file_node: NodeFactory,
    make_edge: EdgeFactory,
) -> None:
    base_report = {
        "ref": "base",
        "nodes": [
            {
                **make_file_node("a.py", outgoing=1),
                "complexityConnections": 1,
                "complexityScore": 0.4,
            },
            {
                **make_file_node("b.py", incoming=1),
                "complexityConnections": 1,
                "complexityScore": 0.2,
            },
        ],
        "edges": [make_edge("a.py", "b.py")],
        "metrics": {
            "circularDependencyCount": 0,
            "complexity": [{"file": "a.py", "score": 0.4}],
        },
        "risks": {
            "top_risk_files": [{"file": "a.py", "riskScore": 10}],
            "layer_violations": [],
            "god_modules": [],
            "dependency_explosions": [],
        },
        "architecture": {
            "health": {"score": 82},
            "detectedStyle": {"name": "monolith"},
            "ruleViolations": [],
        },
        "simple": {"edges": [["a.py", "b.py"]]},
    }
    head_report = {
        "ref": "head",
        "nodes": [
            {
                **make_file_node("a.py", outgoing=1),
                "complexityConnections": 1,
                "complexityScore": 0.6,
            },
            {
                **make_file_node("b.py"),
                "complexityConnections": 0,
                "complexityScore": 0.0,
            },
            {
                **make_file_node("c.py", incoming=1),
                "complexityConnections": 1,
                "complexityScore": 0.2,
            },
        ],
        "edges": [make_edge("a.py", "c.py")],
        "metrics": {
            "circularDependencyCount": 0,
            "complexity": [{"file": "a.py", "score": 0.6}],
        },
        "risks": {
            "top_risk_files": [{"file": "a.py", "riskScore": 13}],
            "layer_violations": [],
            "god_modules": [],
            "dependency_explosions": [],
        },
        "architecture": {
            "health": {"score": 76},
            "detectedStyle": {"name": "modular_monolith"},
            "ruleViolations": [{"rule": "controller -> repository"}],
        },
        "simple": {"edges": [["a.py", "c.py"]]},
    }

    diff = diff_reports(base_report, head_report)

    assert diff["files"]["added"] == ["c.py"]
    assert diff["files"]["removed"] == []
    assert diff["files"]["delta"] == 1
    assert diff["riskSummary"]["headTopRisks"] == 1
    assert diff["architecture"] == {
        "baseHealth": 82,
        "headHealth": 76,
        "healthDelta": -6,
        "baseStyle": "monolith",
        "headStyle": "modular_monolith",
        "styleChanged": True,
        "ruleViolationsDelta": 1,
    }
    assert diff["edges"]["added"] == [("a.py", "c.py")]
    assert diff["edges"]["removed"] == [("a.py", "b.py")]
    assert diff["files"]["changed"] == [
        {
            "file": "a.py",
            "outgoingDelta": 0,
            "incomingDelta": 0,
            "totalConnectionsDelta": 0,
            "complexityDelta": 0.2,
            "riskScoreDelta": 3,
            "addedDependencies": ["c.py"],
            "removedDependencies": ["b.py"],
        },
        {
            "file": "b.py",
            "outgoingDelta": 0,
            "incomingDelta": -1,
            "totalConnectionsDelta": -1,
            "complexityDelta": -0.2,
            "riskScoreDelta": 0,
            "addedDependencies": [],
            "removedDependencies": [],
        },
    ]


def _git(repo: Path, *args: str) -> None:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "git command failed"
        raise RuntimeError(message)


def test_normalize_report_uses_detailed_nodes() -> None:
    exported = {
        "nodes": ["a.py"],
        "edges": [["a.py", "b.py"]],
        "detailed": {
            "nodes": [{"id": "a.py", "type": "file"}],
            "edges": [{"source": "a.py", "target": "b.py"}],
        },
        "metrics": {},
    }
    report = normalize_report(exported)
    assert report["nodes"] == [{"id": "a.py", "type": "file"}]
    assert report["edges"] == [{"source": "a.py", "target": "b.py"}]
    assert report["simple"] == {"nodes": ["a.py"], "edges": [["a.py", "b.py"]]}


def test_normalize_report_keeps_in_memory_shape() -> None:
    in_memory = {"nodes": [{"id": "a.py", "type": "file"}], "edges": [], "metrics": {}}
    assert normalize_report(in_memory)["nodes"] == in_memory["nodes"]


def _report(findings=None, nodes=None, tested_ratio=None, grade="B", score=80) -> dict:
    report: dict = {
        "nodes": nodes or [],
        "edges": [],
        "simple": {"nodes": [n["id"] for n in (nodes or [])], "edges": []},
        "metrics": {"circularDependencyCount": 0},
        "architecture": {"health": {"score": score, "grade": grade}},
    }
    if tested_ratio is not None:
        report["metrics"]["testMapping"] = {"testedRatio": tested_ratio}
    if findings is not None:
        report["findings"] = findings
    return report


def _finding(category: str, key: str, severity: str = "medium", **extra) -> dict:
    return {"id": "X-001", "category": category, "severity": severity, "message": category,
            "evidence": [], "key": key, **extra}


def test_diff_new_and_resolved_findings() -> None:
    shared = _finding("layer_violation", "layer_violation|x|y", source="x", target="y")
    base = _report(findings=[_finding("god_module", "god_module|a.py", file="a.py"), shared])
    head = _report(findings=[
        shared,
        _finding("structural_bottleneck", "structural_bottleneck|b.py", "high", file="b.py"),
    ])
    diff = diff_reports(base, head)
    assert diff["findingsComparable"] is True
    assert [f["key"] for f in diff["findings"]["new"]] == ["structural_bottleneck|b.py"]
    assert [f["key"] for f in diff["findings"]["resolved"]] == ["god_module|a.py"]
    assert diff["findings"]["unchanged"] == 1
    assert [f["key"] for f in diff["bottlenecks"]["new"]] == ["structural_bottleneck|b.py"]


def test_diff_orders_new_findings_by_severity() -> None:
    head = _report(findings=[
        _finding("god_module", "god_module|z.py", "low", file="z.py"),
        _finding("god_module", "god_module|a.py", "critical", file="a.py"),
        _finding("god_module", "god_module|m.py", "high", file="m.py"),
    ])
    diff = diff_reports(_report(findings=[]), head)
    assert [f["severity"] for f in diff["findings"]["new"]] == ["critical", "high", "low"]


def test_diff_lost_coverage() -> None:
    base = _report(findings=[], tested_ratio=0.5, nodes=[
        {"id": "a.py", "type": "file", "testedBy": ["tests/test_a.py"]},
        {"id": "b.py", "type": "file", "testedBy": []},
    ])
    head = _report(findings=[], tested_ratio=0.0, nodes=[
        {"id": "a.py", "type": "file", "testedBy": []},
        {"id": "b.py", "type": "file", "testedBy": []},
    ])
    diff = diff_reports(base, head)
    assert diff["tests"]["lostCoverage"] == [{"file": "a.py", "testedBy": ["tests/test_a.py"]}]
    assert diff["tests"]["baseTestedRatio"] == 0.5
    assert diff["tests"]["headTestedRatio"] == 0.0


def test_diff_without_findings_is_not_comparable() -> None:
    base = _report()  # a report written before findings were exported
    head = _report(findings=[_finding("god_module", "god_module|a.py", file="a.py")])
    diff = diff_reports(base, head)
    assert diff["findingsComparable"] is False
    assert "findings" not in diff
    assert diff["tests"]["baseTestedRatio"] is None


def test_diff_exposes_grades() -> None:
    diff = diff_reports(_report(grade="B", score=80), _report(grade="C", score=64))
    assert diff["grades"] == {"base": "B", "head": "C"}


def _node(file_id: str, outgoing: int, incoming: int = 0) -> dict:
    return {"id": file_id, "type": "file", "outgoing": outgoing, "incoming": incoming}


def test_diff_moves_threshold_shift_findings_out_of_new() -> None:
    # Same file, same outgoing count: flagged only because the project-relative
    # threshold moved (e.g. the PR added leaf files elsewhere).
    base = _report(findings=[], nodes=[_node("a.py", 9)])
    head = _report(
        findings=[_finding("god_module", "god_module|a.py", file="a.py")],
        nodes=[_node("a.py", 9), _node("new_leaf.py", 0)],
    )
    diff = diff_reports(base, head)
    assert diff["findings"]["new"] == []
    shifted = diff["findings"]["thresholdShift"]
    assert [(f["key"], f["direction"]) for f in shifted] == [("god_module|a.py", "new")]


def test_diff_keeps_real_new_god_module() -> None:
    base = _report(findings=[], nodes=[_node("a.py", 3)])
    head = _report(
        findings=[_finding("god_module", "god_module|a.py", file="a.py")],
        nodes=[_node("a.py", 12)],
    )
    diff = diff_reports(base, head)
    assert [f["key"] for f in diff["findings"]["new"]] == ["god_module|a.py"]
    assert diff["findings"]["thresholdShift"] == []


def test_diff_moves_threshold_shift_out_of_resolved() -> None:
    base = _report(
        findings=[_finding("dependency_explosion", "dependency_explosion|c.py", file="c.py")],
        nodes=[_node("c.py", 7, 7)],
    )
    head = _report(findings=[], nodes=[_node("c.py", 7, 7)])
    diff = diff_reports(base, head)
    assert diff["findings"]["resolved"] == []
    assert [f["direction"] for f in diff["findings"]["thresholdShift"]] == ["resolved"]


def test_diff_new_file_god_module_is_real() -> None:
    base = _report(findings=[], nodes=[])
    head = _report(
        findings=[_finding("god_module", "god_module|n.py", file="n.py")],
        nodes=[_node("n.py", 20)],
    )
    assert [f["key"] for f in diff_reports(base, head)["findings"]["new"]] == ["god_module|n.py"]
