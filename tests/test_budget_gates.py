from __future__ import annotations

from argparse import Namespace

from archmap.cli.reporting import _evaluate_budget_violations, evaluate_quality_gates
from archmap.config import load_project_config


def _file_node(file_id: str, *, outgoing: int = 0, incoming: int = 0) -> dict:
    return {
        "id": file_id, "label": file_id, "type": "file",
        "outgoing": outgoing, "incoming": incoming,
    }


def _make_report(nodes: list[dict], *, config_budgets: dict | None = None) -> dict:
    report: dict = {
        "metrics": {
            "filesAnalyzed": len(nodes),
            "totalDependencies": 0,
            "circularDependencyCount": 0,
            "resolutionRate": 1.0,
            "complexity": [],
        },
        "nodes": nodes,
        "risks": {},
        "architecture": {
            "health": {"score": 100, "grade": "A"},
            "ruleViolations": [],
            "activeRules": {"forbid": [], "allow": []},
        },
    }
    if config_budgets:
        report["_configBudgets"] = config_budgets
    return report


def _args(*, fail: bool = True, max_out: int | None = None, max_in: int | None = None) -> Namespace:
    return Namespace(
        fail_on_budget_violations=fail,
        max_outgoing_per_file=max_out,
        max_incoming_per_file=max_in,
        fail_on_cycles=False,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=False,
        min_health=None,
        min_resolution_rate=None,
    )


def test_no_violations_when_within_limits() -> None:
    nodes = [_file_node("a.py", outgoing=3, incoming=1)]
    failures = evaluate_quality_gates(_make_report(nodes), _args(max_out=5, max_in=5))
    assert failures == []


def test_outgoing_violation_detected() -> None:
    nodes = [_file_node("fat.py", outgoing=10)]
    failures = _evaluate_budget_violations(
        _make_report(nodes),
        Namespace(max_outgoing_per_file=5, max_incoming_per_file=None),
    )
    assert len(failures) == 1
    assert "outgoing" in failures[0]
    assert "fat.py" in failures[0]


def test_incoming_violation_detected() -> None:
    nodes = [_file_node("hub.py", incoming=20)]
    failures = _evaluate_budget_violations(
        _make_report(nodes),
        Namespace(max_outgoing_per_file=None, max_incoming_per_file=10),
    )
    assert len(failures) == 1
    assert "incoming" in failures[0]
    assert "hub.py" in failures[0]


def test_budget_falls_back_to_config_budgets() -> None:
    nodes = [_file_node("heavy.py", outgoing=15)]
    report = _make_report(nodes, config_budgets={"max_outgoing_per_file": 10})
    failures = _evaluate_budget_violations(
        report,
        Namespace(max_outgoing_per_file=None, max_incoming_per_file=None),
    )
    assert len(failures) == 1
    assert "heavy.py" in failures[0]


def test_cli_override_takes_precedence_over_config() -> None:
    nodes = [_file_node("a.py", outgoing=6)]
    report = _make_report(nodes, config_budgets={"max_outgoing_per_file": 10})
    # CLI says 5, config says 10 — CLI should win, causing a violation
    failures = _evaluate_budget_violations(
        report,
        Namespace(max_outgoing_per_file=5, max_incoming_per_file=None),
    )
    assert len(failures) == 1


def test_no_violation_when_no_budgets_set() -> None:
    nodes = [_file_node("a.py", outgoing=999)]
    failures = _evaluate_budget_violations(
        _make_report(nodes),
        Namespace(max_outgoing_per_file=None, max_incoming_per_file=None),
    )
    assert failures == []


def test_package_nodes_are_ignored_by_budget_check() -> None:
    nodes = [
        _file_node("a.py", outgoing=1),
        {"id": "pkg:requests", "type": "package", "outgoing": 999, "incoming": 0},
    ]
    failures = _evaluate_budget_violations(
        _make_report(nodes),
        Namespace(max_outgoing_per_file=5, max_incoming_per_file=None),
    )
    assert failures == []


def test_config_budgets_parsed_from_toml(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        "[analysis.budgets]\nmax_outgoing_per_file = 8\nmax_incoming_per_file = 12\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config["analysis"]["budgets"]["max_outgoing_per_file"] == 8
    assert config["analysis"]["budgets"]["max_incoming_per_file"] == 12


def test_config_budgets_absent_has_no_active_limits(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text("[analysis]\n", encoding="utf-8")
    config = load_project_config(tmp_path)
    budgets = config["analysis"]["budgets"]
    # When no [analysis.budgets] section is defined, no positive limits are set
    active = {k: v for k, v in budgets.items() if v is not None}
    assert active == {}


def test_gate_reports_multiple_violators() -> None:
    nodes = [
        _file_node("a.py", outgoing=20),
        _file_node("b.py", outgoing=30),
    ]
    failures = _evaluate_budget_violations(
        _make_report(nodes),
        Namespace(max_outgoing_per_file=10, max_incoming_per_file=None),
    )
    assert len(failures) == 1
    assert "2 file(s)" in failures[0]
