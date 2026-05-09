from __future__ import annotations

import argparse

import pytest

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project


# ── helpers ──────────────────────────────────────────────────────────────────

def _analyze(virtual: dict[str, str]) -> dict:
    parsed = parse_project(".", virtual_files=virtual)
    graph = build_graph(parsed)
    return analyze_graph(graph)


def _make_gate_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        fail_on_cycles=False,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=False,
        min_health=None,
        min_resolution_rate=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ── resolution rate metric ────────────────────────────────────────────────────

def test_resolution_rate_in_metrics():
    report = _analyze({"a.py": "import b\n", "b.py": ""})
    assert "resolutionRate" in report["metrics"]


def test_resolution_rate_all_internal():
    """All imports resolve to internal project files → rate is 1.0."""
    report = _analyze({"a.py": "import b\n", "b.py": ""})
    assert report["metrics"]["resolutionRate"] == 1.0


def test_resolution_rate_external_packages_count_as_resolved():
    """External-package imports still resolve to package nodes → rate stays 1.0."""
    report = _analyze({"a.py": "import requests\nimport numpy\n"})
    assert report["metrics"]["resolutionRate"] == 1.0


def test_resolution_rate_no_imports():
    """Files with no imports → rate defaults to 1.0 (no attempt = no failure)."""
    report = _analyze({"a.py": "x = 1\n", "b.py": "y = 2\n"})
    assert report["metrics"]["resolutionRate"] == 1.0


def test_resolution_rate_in_range():
    """Resolution rate is always between 0.0 and 1.0."""
    report = _analyze({"a.py": "from . import utils\n"})
    rate = report["metrics"]["resolutionRate"]
    assert 0.0 <= rate <= 1.0


def test_resolution_rate_empty_project():
    """Empty virtual project has no files → rate defaults to 1.0."""
    report = _analyze({})
    assert report["metrics"]["resolutionRate"] == 1.0


def test_import_stats_propagate_through_graph_builder():
    """importStats must be present in the raw graph produced by build_graph."""
    parsed = parse_project(".", virtual_files={"a.py": "import b\n", "b.py": ""})
    graph = build_graph(parsed)
    assert "importStats" in graph
    assert isinstance(graph["importStats"]["total"], int)
    assert isinstance(graph["importStats"]["resolved"], int)
    assert graph["importStats"]["total"] >= 0
    assert graph["importStats"]["resolved"] >= 0


# ── --min-resolution-rate quality gate ───────────────────────────────────────

def test_gate_passes_when_above_threshold():
    from archmap.cli.reporting import evaluate_quality_gates
    report = _analyze({"a.py": "import b\n", "b.py": ""})
    args = _make_gate_args(min_resolution_rate=70)
    assert evaluate_quality_gates(report, args) == []


def test_gate_passes_when_threshold_is_none():
    from archmap.cli.reporting import evaluate_quality_gates
    report = _analyze({"a.py": "import requests\n"})
    args = _make_gate_args(min_resolution_rate=None)
    assert evaluate_quality_gates(report, args) == []


def test_gate_message_contains_resolution_rate():
    from archmap.cli.reporting import evaluate_quality_gates
    # Build a report with known rate and force the threshold above it
    report = _analyze({"a.py": "import b\n", "b.py": ""})
    # Override rate to simulate low resolution
    report["metrics"]["resolutionRate"] = 0.50
    args = _make_gate_args(min_resolution_rate=70)
    failures = evaluate_quality_gates(report, args)
    assert len(failures) == 1
    assert "resolution-rate" in failures[0]
    assert "50" in failures[0]
    assert "70" in failures[0]


def test_gate_does_not_trigger_at_exact_threshold():
    from archmap.cli.reporting import evaluate_quality_gates
    report = _analyze({"a.py": ""})
    report["metrics"]["resolutionRate"] = 0.70
    args = _make_gate_args(min_resolution_rate=70)
    # 70% == 70% threshold → should NOT fail
    assert evaluate_quality_gates(report, args) == []
