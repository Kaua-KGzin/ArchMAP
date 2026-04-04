from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from archmap.core.analyzer.diff_analyzer import analyze_git_ref, diff_reports

NodeFactory = Callable[..., dict]
EdgeFactory = Callable[..., dict]


def test_diff_reports_detects_dependency_and_cycle_changes(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.email", "archmap@example.com")
    _git(repo, "config", "user.name", "ArchMAP Test")

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
