from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from archmap.cli import commands as cli_commands


def test_run_analyze_prints_summary_and_hint(monkeypatch, capsys) -> None:
    report = {"metrics": {}, "risks": {}}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(
        cli_commands,
        "export_outputs",
        lambda **kwargs: calls.append(("export", kwargs)) or {"jsonPath": "out.json"},
    )
    monkeypatch.setattr(
        cli_commands,
        "print_summary",
        lambda payload, **_kw: calls.append(("summary", payload)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_top_complexity",
        lambda payload, limit: calls.append(("complexity", limit)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_top_risks",
        lambda payload, limit: calls.append(("risks", limit)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_export_summary",
        lambda payload: calls.append(("exports", payload)),
    )
    monkeypatch.setattr(cli_commands, "evaluate_quality_gates", lambda _report, _args: [])

    args = Namespace(
        path="repo",
        format="json",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        include_insights=True,
        include_explanation=True,
        top=-4,
    )

    exit_code = cli_commands.run_analyze(args)

    output = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        (
            "export",
            {
                "report": report,
                "output_format": "json",
                "json_output": "graph.json",
                "mermaid_output": "graph.mmd",
                "cytoscape_output": "graph-cytoscape.json",
                "include_cytoscape": False,
                "no_subgraphs": False,
                "sarif_output": None,
            },
        ),
        ("summary", report),
        ("complexity", 0),
        ("risks", 0),
        ("exports", {"jsonPath": "out.json"}),
    ]
    assert output.err == ""
    assert '[hint] Run "archmap serve <path>" to open the interactive graph.' in output.out


def test_run_analyze_returns_2_when_quality_gate_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli_commands,
        "analyze_project",
        lambda _path, **kwargs: {"metrics": {}, "risks": {}},
    )
    monkeypatch.setattr(cli_commands, "export_outputs", lambda **_kwargs: {})
    monkeypatch.setattr(cli_commands, "print_summary", lambda _payload, **_kw: None)
    monkeypatch.setattr(cli_commands, "print_top_complexity", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_top_risks", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_export_summary", lambda _payload: None)
    monkeypatch.setattr(
        cli_commands,
        "evaluate_quality_gates",
        lambda _report, _args: ["cycle gate failed: 2 circular dependencies found"],
    )

    args = Namespace(
        path="repo",
        format="json",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        include_insights=True,
        include_explanation=True,
        top=5,
    )

    exit_code = cli_commands.run_analyze(args)

    output = capsys.readouterr()
    assert exit_code == 2
    assert output.out == ""
    assert "[gate] cycle gate failed: 2 circular dependencies found" in output.err


def test_run_serve_raises_when_static_dir_is_missing(monkeypatch, tmp_path) -> None:
    state = type("State", (), {"path": tmp_path, "report": {"graph": True}})()

    class StubReportState:
        @classmethod
        def from_path(cls, _path, **kwargs):
            return state

    monkeypatch.setattr(cli_commands, "ReportState", StubReportState)
    monkeypatch.setattr(cli_commands, "export_outputs", lambda **_kwargs: {})
    monkeypatch.setattr(cli_commands, "print_summary", lambda _payload, **_kw: None)
    monkeypatch.setattr(cli_commands, "print_top_complexity", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_top_risks", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_export_summary", lambda _payload: None)
    monkeypatch.setattr(cli_commands, "resolve_static_dir", lambda: tmp_path / "missing")

    args = Namespace(
        path="repo",
        format="both",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        host="127.0.0.1",
        port=3000,
        no_open=False,
    )

    try:
        cli_commands.run_serve(args)
    except RuntimeError as exc:
        assert "Web UI static directory not found" in str(exc)
    else:
        raise AssertionError("run_serve should raise when static dir is missing")


def test_run_serve_starts_server_and_closes_cleanly(monkeypatch, tmp_path, capsys) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = type("State", (), {"path": tmp_path / "repo", "report": {"graph": True}})()
    seen: dict[str, object] = {}

    class StubReportState:
        @classmethod
        def from_path(cls, _path, **kwargs):
            return state

    class FakeServer:
        def __init__(self, address, handler):
            seen["address"] = address
            seen["handler"] = handler
            seen["server_close_calls"] = 0

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            seen["server_close_calls"] = int(seen["server_close_calls"]) + 1

    monkeypatch.setattr(cli_commands, "ReportState", StubReportState)
    monkeypatch.setattr(
        cli_commands,
        "export_outputs",
        lambda **_kwargs: {"jsonPath": "graph.json", "mermaidPath": None, "cytoscapePath": None},
    )
    monkeypatch.setattr(cli_commands, "print_summary", lambda _payload, **_kw: None)
    monkeypatch.setattr(cli_commands, "print_top_complexity", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_top_risks", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_export_summary", lambda _payload: None)
    monkeypatch.setattr(cli_commands, "resolve_static_dir", lambda: static_dir)
    monkeypatch.setattr(cli_commands, "build_http_handler", lambda _state, _static_dir: "handler")
    monkeypatch.setattr(cli_commands, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(cli_commands, "browser_host", lambda _host: "localhost")
    monkeypatch.setattr(cli_commands, "can_open_browser", lambda _host: True)
    monkeypatch.setattr(
        cli_commands.webbrowser,
        "open",
        lambda url, new, autoraise: seen.update(
            {"browser_url": url, "browser_new": new, "browser_autoraise": autoraise}
        ),
    )

    args = Namespace(
        path="repo",
        format="both",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        host="0.0.0.0",
        port=4321,
        no_open=False,
    )

    exit_code = cli_commands.run_serve(args)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert seen == {
        "address": ("0.0.0.0", 4321),
        "handler": "handler",
        "server_close_calls": 1,
        "browser_url": "http://localhost:4321",
        "browser_new": 2,
        "browser_autoraise": False,
    }
    assert "[info] ArchMAP Service Map v" in output
    assert f"[info] Analyzing: {state.path}" in output
    assert "[info] Web UI available at http://localhost:4321" in output
    assert "[info] Listening on http://0.0.0.0:4321" in output
    assert "[info] Press Ctrl+C to stop." in output
    assert "[info] Shutting down server." in output


def test_run_explain_outputs_json(monkeypatch, capsys) -> None:
    report = {
        "projectRoot": "repo",
        "metrics": {"filesAnalyzed": 4},
        "architecture": {"health": {"score": 92}},
        "insights": {"status": "ok"},
        "explanation": {"simple": "Simple view"},
    }
    suggestions = {
        "simpleMap": {"auth": ["users", "payments"]},
        "groups": [{"name": "auth", "count": 2}],
    }

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(
        cli_commands,
        "suggest_architecture",
        lambda payload, max_groups: suggestions,
    )

    args = Namespace(path="repo", json=True, max_groups=6, parallel=True)

    exit_code = cli_commands.run_explain(args)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "projectRoot": "repo",
        "summary": {"filesAnalyzed": 4},
        "architecture": {"health": {"score": 92}},
        "insights": {"status": "ok"},
        "explanation": {"simple": "Simple view"},
        "simpleMap": {"auth": ["users", "payments"]},
        "suggestions": [{"name": "auth", "count": 2}],
    }


def test_run_explain_prints_simple_view(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    report = {
        "metrics": {"filesAnalyzed": 4, "totalDependencies": 3, "circularDependencyCount": 0},
        "architecture": {},
        "insights": {},
        "explanation": {},
    }
    suggestions = {"simpleMap": {"auth": ["users"]}}

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(
        cli_commands,
        "suggest_architecture",
        lambda payload, max_groups: suggestions,
    )
    monkeypatch.setattr(
        cli_commands,
        "print_summary",
        lambda payload, **_kw: calls.append(("summary", payload)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_human_insights",
        lambda payload: calls.append(("insights", payload)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_project_explanation",
        lambda payload: calls.append(("explanation", payload)),
    )
    monkeypatch.setattr(
        cli_commands,
        "print_simple_map",
        lambda payload: calls.append(("simple_map", payload)),
    )

    args = Namespace(path="repo", json=False, max_groups=5, parallel=True)

    exit_code = cli_commands.run_explain(args)

    assert exit_code == 0
    assert calls == [
        ("summary", report),
        ("insights", report),
        ("explanation", report),
        ("simple_map", {"auth": ["users"]}),
    ]


def test_run_risk_outputs_json(monkeypatch, capsys) -> None:
    report = {
        "projectRoot": "repo",
        "nodes": [
            {
                "id": "src/auth.ts",
                "type": "file",
                "incoming": 2,
                "outgoing": 3,
                "isCircular": True,
                "impact": {
                    "impactCount": 2,
                    "impactedFiles": ["src/user.ts", "src/payments.ts"],
                },
            }
        ],
        "risks": {
            "top_risk_files": [
                {
                    "file": "src/auth.ts",
                    "riskScore": 84,
                    "signals": ["cycle", "hub"],
                }
            ]
        },
    }

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)

    args = Namespace(
        target="src/auth.ts",
        path="repo",
        json=True,
        max_impacted=10,
        parallel=True,
    )

    exit_code = cli_commands.run_risk(args)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "file": "src/auth.ts",
        "incoming": 2,
        "outgoing": 3,
        "isCircular": True,
        "impact": {
            "impactCount": 2,
            "impactedFiles": ["src/user.ts", "src/payments.ts"],
        },
        "riskScore": 84,
        "signals": ["cycle", "hub"],
    }


def test_run_risk_reports_missing_file(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli_commands,
        "analyze_project",
        lambda path, **kwargs: {"projectRoot": "repo", "nodes": [], "risks": {}},
    )

    args = Namespace(
        target="src/missing.ts",
        path="repo",
        json=False,
        max_impacted=10,
        parallel=True,
    )

    exit_code = cli_commands.run_risk(args)

    output = capsys.readouterr()
    assert exit_code == 1
    assert "[error] File not found in analyzed project: src/missing.ts" in output.err


def test_run_improve_writes_script_and_outputs_json(monkeypatch, tmp_path, capsys) -> None:
    report = {"projectRoot": "repo"}
    suggestions = {
        "summary": "Suggested architecture groups: /auth, /payments.",
        "simpleMap": {"auth": ["payments"]},
        "groups": [{"name": "auth", "count": 2}],
        "moves": [{"source": "src/auth.ts", "target": "auth/auth.ts", "group": "auth"}],
        "suggestedLayout": {"auth": ["auth/auth.ts"]},
    }
    script_path = tmp_path / "refactor.ps1"

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(
        cli_commands,
        "suggest_architecture",
        lambda payload, max_groups: suggestions,
    )
    monkeypatch.setattr(
        cli_commands,
        "generate_refactor_script",
        lambda payload: "# script\nMove-Item 'src/auth.ts' 'auth/auth.ts'\n",
    )

    args = Namespace(
        path="repo",
        json=True,
        max_groups=6,
        out_script=str(script_path),
        parallel=True,
    )

    exit_code = cli_commands.run_improve(args)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert script_path.read_text(encoding="utf-8").startswith("# script")
    assert payload == {
        "projectRoot": "repo",
        "summary": "Suggested architecture groups: /auth, /payments.",
        "simpleMap": {"auth": ["payments"]},
        "groups": [{"name": "auth", "count": 2}],
        "moves": [{"source": "src/auth.ts", "target": "auth/auth.ts", "group": "auth"}],
        "suggestedLayout": {"auth": ["auth/auth.ts"]},
        "scriptPath": str(script_path.resolve()),
    }


def test_run_diff_resolves_repo_and_prints_result(monkeypatch, tmp_path) -> None:
    seen: list[tuple[Path, str]] = []

    def fake_analyze_git_ref(repo_root: Path, ref: str) -> dict:
        seen.append((repo_root, ref))
        return {"nodes": [], "ref": "placeholder"}

    monkeypatch.setattr(cli_commands, "analyze_git_ref", fake_analyze_git_ref)
    monkeypatch.setattr(
        cli_commands,
        "diff_reports",
        lambda base_report, head_report: {
            "baseRef": base_report["ref"],
            "headRef": head_report["ref"],
        },
    )
    printed: dict[str, object] = {}
    monkeypatch.setattr(
        cli_commands,
        "print_diff_output",
        lambda base_ref, head_ref, diff_result, as_json: printed.update(
            {
                "base_ref": base_ref,
                "head_ref": head_ref,
                "diff_result": diff_result,
                "as_json": as_json,
            }
        ),
    )

    args = Namespace(
        repo=str(tmp_path),
        base_ref="main",
        head_ref="feature",
        json=True,
    )

    exit_code = cli_commands.run_diff(args)

    assert exit_code == 0
    assert seen == [
        (tmp_path.resolve(), "main"),
        (tmp_path.resolve(), "feature"),
    ]
    assert printed == {
        "base_ref": "main",
        "head_ref": "feature",
        "diff_result": {"baseRef": "main", "headRef": "feature"},
        "as_json": True,
    }


def test_run_history_resolves_repo_and_prints_result(monkeypatch, tmp_path) -> None:
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        cli_commands,
        "analyze_git_history",
        lambda repo_root, ref, limit: seen.update(
            {"repo_root": repo_root, "ref": ref, "limit": limit}
        )
        or {"snapshots": []},
    )
    monkeypatch.setattr(
        cli_commands,
        "print_history_output",
        lambda history, as_json: seen.update({"history": history, "as_json": as_json}),
    )

    args = Namespace(
        repo=str(tmp_path),
        ref="HEAD~3",
        limit=8,
        json=True,
    )

    exit_code = cli_commands.run_history(args)

    assert exit_code == 0
    assert seen == {
        "repo_root": tmp_path.resolve(),
        "ref": "HEAD~3",
        "limit": 8,
        "history": {"snapshots": []},
        "as_json": True,
    }


def test_run_analyze_quiet_suppresses_output(monkeypatch, capsys) -> None:
    empty_report = {"metrics": {}, "risks": {}}
    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: empty_report)
    monkeypatch.setattr(cli_commands, "export_outputs", lambda **kwargs: {"jsonPath": "out.json"})
    monkeypatch.setattr(cli_commands, "evaluate_quality_gates", lambda _report, _args: [])

    args = Namespace(
        path="repo",
        format="json",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        include_insights=True,
        include_explanation=True,
        top=5,
        quiet=True,
    )

    exit_code = cli_commands.run_analyze(args)

    output = capsys.readouterr()
    assert exit_code == 0
    assert output.out == ""
    assert output.err == ""


def test_run_risk_prints_report_when_not_json(monkeypatch, capsys) -> None:
    report = {
        "projectRoot": "repo",
        "nodes": [
            {
                "id": "src/app.py",
                "type": "file",
                "incoming": 1,
                "outgoing": 2,
                "isCircular": False,
                "impact": {"impactCount": 1, "impactedFiles": ["src/utils.py"]},
            }
        ],
        "risks": {
            "top_risk_files": [
                {"file": "src/app.py", "riskScore": 45, "signals": ["hub"]}
            ]
        },
    }

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)

    args = Namespace(
        target="src/app.py",
        path="repo",
        json=False,
        max_impacted=10,
        parallel=True,
    )

    exit_code = cli_commands.run_risk(args)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[risk] src/app.py" in output
    assert "Risk score: 45" in output
    assert "Signals: hub" in output


def test_run_serve_starts_watch_thread(monkeypatch, tmp_path, capsys) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = type("State", (), {"path": tmp_path / "repo", "report": {}})()

    class StubReportState:
        @classmethod
        def from_path(cls, _path, **kwargs):
            return state

    class FakeServer:
        def __init__(self, address, handler):
            pass

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    thread_targets: list[object] = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            thread_targets.append(target)
            self._daemon = daemon

        def start(self) -> None:
            pass

    monkeypatch.setattr(cli_commands, "ReportState", StubReportState)
    monkeypatch.setattr(cli_commands, "export_outputs", lambda **_kwargs: {})
    monkeypatch.setattr(cli_commands, "print_summary", lambda _payload, **_kw: None)
    monkeypatch.setattr(cli_commands, "print_top_complexity", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_top_risks", lambda _payload, _limit: None)
    monkeypatch.setattr(cli_commands, "print_export_summary", lambda _payload: None)
    monkeypatch.setattr(cli_commands, "resolve_static_dir", lambda: static_dir)
    monkeypatch.setattr(cli_commands, "build_http_handler", lambda _state, _static_dir: "handler")
    monkeypatch.setattr(cli_commands, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(cli_commands, "browser_host", lambda _host: "localhost")
    monkeypatch.setattr(cli_commands, "can_open_browser", lambda _host: False)
    monkeypatch.setattr(cli_commands, "threading", type("T", (), {"Thread": FakeThread})())

    args = Namespace(
        path="repo",
        format="json",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        host="127.0.0.1",
        port=5000,
        no_open=True,
        watch=True,
    )

    exit_code = cli_commands.run_serve(args)
    assert exit_code == 0
    assert len(thread_targets) == 1


def test_run_analyze_with_impact_flag(monkeypatch, capsys) -> None:
    report = {
        "metrics": {
            "filesAnalyzed": 2, "totalDependencies": 1,
            "circularDependencyCount": 0, "complexity": [],
        },
        "risks": {"top_risk_files": []},
        "nodes": [
            {
                "id": "src/auth.py",
                "impact": {"impactedFiles": ["src/app.py"], "impactCount": 1, "risk": "medium"},
            }
        ],
    }

    _export_result = {"jsonPath": "out.json", "mermaidPath": None, "cytoscapePath": None}

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(cli_commands, "export_outputs", lambda **kwargs: _export_result)
    monkeypatch.setattr(cli_commands, "evaluate_quality_gates", lambda _report, _args: [])

    args = Namespace(
        path="repo",
        format="json",
        out="graph.json",
        out_mermaid="graph.mmd",
        out_cytoscape="graph-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=False,
        include_insights=False,
        include_explanation=False,
        top=0,
        quiet=False,
        impact="src/auth.py",
    )

    exit_code = cli_commands.run_analyze(args)
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[risk] Impact analysis for src/auth.py" in output


def test_run_improve_prints_report_when_not_json(monkeypatch, capsys) -> None:
    report = {"projectRoot": "repo"}
    suggestions = {
        "summary": "2 groups suggested",
        "simpleMap": {"auth": ["users"]},
        "groups": [{"name": "auth", "count": 2}],
        "moves": [],
        "suggestedLayout": {},
    }

    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: report)
    monkeypatch.setattr(
        cli_commands, "suggest_architecture", lambda payload, max_groups: suggestions
    )

    args = Namespace(
        path="repo",
        json=False,
        max_groups=6,
        out_script=None,
        parallel=True,
    )

    exit_code = cli_commands.run_improve(args)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[improve] Automatic architecture suggestions" in output
    assert "[map] Simple architecture view" in output


def test_run_init_handles_oserror_scanning(monkeypatch, tmp_path, capsys) -> None:
    import os as _os

    def raise_oserror(path):
        raise OSError("permission denied")

    monkeypatch.setattr(_os, "scandir", raise_oserror)

    args = Namespace(
        path=str(tmp_path),
        dry_run=False,
        force=True,
    )

    exit_code = cli_commands.run_init(args)

    output = capsys.readouterr()
    assert exit_code == 1
    assert "[error]" in output.err
    assert "permission denied" in output.err


def test_serve_watch_loop_detects_change_and_handles_error(monkeypatch, capsys) -> None:
    import itertools

    call_counter = itertools.count()

    class FakeState:
        path = Path(".")

        def reanalyze(self) -> None:
            raise RuntimeError("disk full")

    def fake_get_mtimes(path):
        n = next(call_counter)
        return {"file.py": float(n)}

    sleep_calls: list[float] = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_commands, "_get_project_mtimes", fake_get_mtimes)
    monkeypatch.setattr(cli_commands.time, "sleep", fake_sleep)
    monkeypatch.setattr(cli_commands.time, "strftime", lambda _: "00:00:01")

    try:
        cli_commands._serve_watch_loop(FakeState())
    except KeyboardInterrupt:
        pass

    output = capsys.readouterr().out
    assert "[error] Watch re-analysis failed: disk full" in output


def test_get_project_mtimes_handles_oserror(monkeypatch, tmp_path) -> None:
    src_file = tmp_path / "app.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    import archmap.utils.file_utils as fu
    monkeypatch.setattr(fu, "discover_source_files", lambda _: [src_file])

    original_stat = Path.stat

    def patched_stat(self, **kwargs):
        if str(self) == str(src_file):
            raise OSError("permission denied")
        return original_stat(self, **kwargs)

    monkeypatch.setattr(Path, "stat", patched_stat)
    result = cli_commands._get_project_mtimes(tmp_path)
    assert isinstance(result, dict)
    assert str(src_file) not in result
