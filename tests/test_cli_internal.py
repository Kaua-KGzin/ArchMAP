from __future__ import annotations

from argparse import Namespace

from archmap.cli import main as cli_main
from archmap.cli.reporting import evaluate_quality_gates, format_diff_output


def test_main_routes_to_version_without_banner_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)

    exit_code = cli_main.main(["version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "archmap " in captured.out


def test_main_applies_default_command_and_routes_to_serve(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_serve(args: Namespace) -> int:
        seen["command"] = args.command
        seen["path"] = args.path
        seen["port"] = args.port
        seen["host"] = args.host
        return 0

    monkeypatch.setattr(cli_main, "_run_serve", fake_run_serve)

    exit_code = cli_main.main([])

    assert exit_code == 0
    assert seen == {
        "command": "serve",
        "path": ".",
        "port": cli_main.DEFAULT_PORT,
        "host": cli_main.DEFAULT_HOST,
    }


def test_main_routes_to_analyze(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_analyze(args: Namespace) -> int:
        seen["command"] = args.command
        seen["path"] = args.path
        return 0

    monkeypatch.setattr(cli_main, "_run_analyze", fake_run_analyze)

    exit_code = cli_main.main(["analyze", "repo"])

    assert exit_code == 0
    assert seen == {"command": "analyze", "path": "repo"}


def test_main_routes_to_diff(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_diff(args: Namespace) -> int:
        seen["command"] = args.command
        seen["base_ref"] = args.base_ref
        seen["head_ref"] = args.head_ref
        return 0

    monkeypatch.setattr(cli_main, "_run_diff", fake_run_diff)

    exit_code = cli_main.main(["diff", "main", "feature"])

    assert exit_code == 0
    assert seen == {
        "command": "diff",
        "base_ref": "main",
        "head_ref": "feature",
    }


def test_main_routes_to_explain(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_explain(args: Namespace) -> int:
        seen["command"] = args.command
        seen["path"] = args.path
        return 0

    monkeypatch.setattr(cli_main, "_run_explain", fake_run_explain)

    exit_code = cli_main.main(["explain", "repo"])

    assert exit_code == 0
    assert seen == {"command": "explain", "path": "repo"}


def test_main_routes_to_risk(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_risk(args: Namespace) -> int:
        seen["command"] = args.command
        seen["target"] = args.target
        return 0

    monkeypatch.setattr(cli_main, "_run_risk", fake_run_risk)

    exit_code = cli_main.main(["risk", "src/auth.ts"])

    assert exit_code == 0
    assert seen == {"command": "risk", "target": "src/auth.ts"}


def test_main_routes_to_improve(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)
    seen: dict[str, object] = {}

    def fake_run_improve(args: Namespace) -> int:
        seen["command"] = args.command
        seen["path"] = args.path
        return 0

    monkeypatch.setattr(cli_main, "_run_improve", fake_run_improve)

    exit_code = cli_main.main(["improve", "repo"])

    assert exit_code == 0
    assert seen == {"command": "improve", "path": "repo"}


def test_main_returns_error_code_when_command_handler_raises(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "_print_banner", lambda: None)

    def raise_boom(_args: Namespace) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "_run_analyze", raise_boom)

    exit_code = cli_main.main(["analyze", "."])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "[error] boom" in captured.err


def test_evaluate_quality_gates_reports_all_enabled_failures() -> None:
    report = {
        "metrics": {"circularDependencyCount": 1},
        "risks": {
            "layer_violations": [{"source": "a", "target": "b"}],
            "god_modules": [{"file": "mod.py"}],
            "dependency_explosions": [{"file": "hub.py"}],
        },
        "architecture": {
            "ruleViolations": [{"rule": "controller -> repository"}],
            "health": {"score": 52},
        },
    }
    args = Namespace(
        fail_on_cycles=True,
        fail_on_layer_violations=True,
        fail_on_god_modules=True,
        fail_on_dependency_explosions=True,
        fail_on_custom_rules=True,
        fail_on_risks=True,
        min_health=60,
    )

    failures = evaluate_quality_gates(report, args)

    assert failures == [
        "cycle gate failed: 1 circular dependencies found",
        "layer gate failed: 1 layer violations found",
        "god-module gate failed: 1 god modules found",
        "dependency-explosion gate failed: 1 dependency explosions found",
        "custom-rule gate failed: 1 custom architecture rule violations found",
        "risk gate failed: detected cycles/layer violations/god modules/"
        "dependency explosions/custom rule violations",
        "health gate failed: architecture health 52 is below 60",
    ]


def test_format_diff_output_renders_signed_summary() -> None:
    diff_result = {
        "edges": {"delta": 3},
        "cycles": {"delta": -1},
        "complexity": {"deltaPercent": 12.5},
        "architecture": {
            "healthDelta": 4,
            "ruleViolationsDelta": -2,
            "styleChanged": False,
        },
        "riskSummary": {
            "layerViolationsDelta": 2,
            "godModulesDelta": 0,
            "dependencyExplosionsDelta": -4,
        },
    }

    output = format_diff_output("main", "feature", diff_result)

    assert output.splitlines() == [
        "Comparing main -> feature",
        "+3 dependencies",
        "-1 circular dependencies",
        "complexity +12.50%",
        "health +4",
        "+2 layer violations",
        "+0 god modules",
        "-4 dependency explosions",
        "-2 custom rule violations",
    ]


def test_main_resolve_command_handler_returns_none_for_unknown_command() -> None:
    assert cli_main._resolve_command_handler("unknown") is None
