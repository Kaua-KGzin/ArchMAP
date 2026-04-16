"""Tests for commands.py - covering watch diff, init rendering, normalize target."""
from __future__ import annotations

from pathlib import Path

from archmap.cli.commands import (
    _build_file_risk_payload,
    _normalize_target_id,
    _print_watch_diff,
    _render_ignore_dirs,
    _render_layer_suggestions,
)


def test_render_ignore_dirs_empty() -> None:
    assert _render_ignore_dirs([]) == "ignore_dirs = []"


def test_render_ignore_dirs_with_entries() -> None:
    result = _render_ignore_dirs(["node_modules", ".venv"])
    assert '"node_modules"' in result
    assert '".venv"' in result


def test_render_layer_suggestions_with_candidates() -> None:
    result = _render_layer_suggestions(["api", "core", "utils"])
    assert "api = 1" in result
    assert "core = 2" in result
    assert "utils = 3" in result


def test_render_layer_suggestions_empty() -> None:
    result = _render_layer_suggestions([])
    assert "api = 1" in result
    assert "core = 2" in result


def test_print_watch_diff_health_change(capsys) -> None:
    old = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [{"id": "a.py", "type": "file"}],
    }
    new = {
        "architecture": {"health": {"score": 70}},
        "cycles": [],
        "nodes": [{"id": "a.py", "type": "file"}],
    }

    _print_watch_diff(old, new)
    output = capsys.readouterr().out
    assert "Health Score" in output


def test_print_watch_diff_cycles_change(capsys) -> None:
    old = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [],
    }
    new = {
        "architecture": {"health": {"score": 80}},
        "cycles": [["a.py", "b.py"]],
        "nodes": [],
    }

    _print_watch_diff(old, new)
    output = capsys.readouterr().out
    assert "Cycles" in output


def test_print_watch_diff_files_added(capsys) -> None:
    old = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [{"id": "a.py", "type": "file"}],
    }
    new = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [
            {"id": "a.py", "type": "file"},
            {"id": "b.py", "type": "file"},
        ],
    }

    _print_watch_diff(old, new)
    output = capsys.readouterr().out
    assert "Added: 1 files" in output


def test_print_watch_diff_files_removed(capsys) -> None:
    old = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [
            {"id": "a.py", "type": "file"},
            {"id": "b.py", "type": "file"},
        ],
    }
    new = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [{"id": "a.py", "type": "file"}],
    }

    _print_watch_diff(old, new)
    output = capsys.readouterr().out
    assert "Removed: 1 files" in output


def test_print_watch_diff_no_change(capsys) -> None:
    old = {
        "architecture": {"health": {"score": 80}},
        "cycles": [],
        "nodes": [{"id": "a.py", "type": "file"}],
    }

    _print_watch_diff(old, old)
    output = capsys.readouterr().out
    assert output == ""


def test_normalize_target_id_relative() -> None:
    result = _normalize_target_id(Path("/project"), "src/main.py")
    assert result == "src/main.py"


def test_normalize_target_id_absolute(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.touch()
    result = _normalize_target_id(project, str(target))
    assert result == "src/app.py"


def test_normalize_target_id_absolute_outside(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    other = tmp_path / "other" / "file.py"
    other.parent.mkdir(parents=True)
    other.touch()
    result = _normalize_target_id(project, str(other))
    assert result == "file.py"


def test_build_file_risk_payload_found() -> None:
    report = {
        "projectRoot": "/project",
        "nodes": [
            {"id": "app.py", "type": "file", "incoming": 3, "outgoing": 5, "isCircular": True,
             "impact": {"impactCount": 2, "impactedFiles": ["b.py"]}},
        ],
        "risks": {
            "top_risk_files": [
                {"file": "app.py", "riskScore": 30, "signals": ["cycle"]},
            ]
        },
    }

    result = _build_file_risk_payload(report, Path("/project"), "app.py")
    assert result is not None
    assert result["file"] == "app.py"
    assert result["incoming"] == 3
    assert result["outgoing"] == 5
    assert result["riskScore"] == 30
    assert result["isCircular"] is True


def test_build_file_risk_payload_not_found() -> None:
    report = {"projectRoot": "/project", "nodes": [], "risks": {}}
    result = _build_file_risk_payload(report, Path("/project"), "missing.py")
    assert result is None


def test_build_file_risk_payload_not_file_type() -> None:
    report = {
        "projectRoot": "/project",
        "nodes": [{"id": "pkg:requests", "type": "package"}],
        "risks": {},
    }
    result = _build_file_risk_payload(report, Path("/project"), "pkg:requests")
    assert result is None
