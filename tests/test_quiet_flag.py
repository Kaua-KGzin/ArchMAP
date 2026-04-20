from __future__ import annotations

import argparse


def _make_analyze_args(
    path: str,
    *,
    quiet: bool = False,
    no_cache: bool = True,
    fail_on_cycles: bool = False,
    format: str = "json",
    top: int = 0,
    include_insights: bool = False,
    include_explanation: bool = False,
    out: str | None = None,
    out_mermaid: str | None = None,
    out_cytoscape: str | None = None,
    include_cytoscape: bool = False,
    no_subgraphs: bool = False,
    sarif: bool = False,
    out_sarif: str | None = None,
    fail_on_layer_violations: bool = False,
    fail_on_god_modules: bool = False,
    fail_on_dependency_explosions: bool = False,
    fail_on_custom_rules: bool = False,
    fail_on_risks: bool = False,
    min_health: int | None = None,
    parallel: bool = True,
    impact: str | None = None,
) -> argparse.Namespace:
    from archmap.cli.defaults import (
        DEFAULT_CYTOSCAPE_OUTPUT_PATH,
        DEFAULT_JSON_OUTPUT_PATH,
        DEFAULT_MERMAID_OUTPUT_PATH,
    )
    ns = argparse.Namespace(
        path=path,
        quiet=quiet,
        no_cache=no_cache,
        format=format,
        top=top,
        include_insights=include_insights,
        include_explanation=include_explanation,
        out=out or DEFAULT_JSON_OUTPUT_PATH,
        out_mermaid=out_mermaid or DEFAULT_MERMAID_OUTPUT_PATH,
        out_cytoscape=out_cytoscape or DEFAULT_CYTOSCAPE_OUTPUT_PATH,
        include_cytoscape=include_cytoscape,
        no_subgraphs=no_subgraphs,
        sarif=sarif,
        out_sarif=out_sarif,
        fail_on_cycles=fail_on_cycles,
        fail_on_layer_violations=fail_on_layer_violations,
        fail_on_god_modules=fail_on_god_modules,
        fail_on_dependency_explosions=fail_on_dependency_explosions,
        fail_on_custom_rules=fail_on_custom_rules,
        fail_on_risks=fail_on_risks,
        min_health=min_health,
        parallel=parallel,
        impact=impact,
    )
    return ns


def test_run_analyze_quiet_suppresses_stdout(capsys, tmp_path, write_project_files):
    write_project_files({"src/main.py": "import os\n"})
    args = _make_analyze_args(str(tmp_path), quiet=True)
    from archmap.cli.commands import run_analyze
    result = run_analyze(args)
    captured = capsys.readouterr()
    assert result == 0
    # No informational output on stdout when quiet
    assert captured.out.strip() == ""


def test_run_analyze_normal_produces_stdout(capsys, tmp_path, write_project_files):
    write_project_files({"src/main.py": "import os\n"})
    args = _make_analyze_args(str(tmp_path), quiet=False)
    from archmap.cli.commands import run_analyze
    result = run_analyze(args)
    captured = capsys.readouterr()
    assert result == 0
    assert len(captured.out) > 0


def test_run_analyze_quiet_still_enforces_gates(capsys, tmp_path, write_project_files):
    write_project_files({
        "src/a.py": "from src import b\n",
        "src/b.py": "from src import a\n",
    })
    args = _make_analyze_args(str(tmp_path), quiet=True, fail_on_cycles=True)
    from archmap.cli.commands import run_analyze
    result = run_analyze(args)
    # Gate failures still printed to stderr even in quiet mode
    captured = capsys.readouterr()
    assert result == 2
    assert "[gate]" in captured.err


def test_quiet_flag_in_cli_args():
    from archmap.cli.args import build_parser
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "--quiet"])
    assert args.quiet is True


def test_quiet_short_flag_in_cli_args():
    from archmap.cli.args import build_parser
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "-q"])
    assert args.quiet is True


def test_no_cache_flag_in_cli_args():
    from archmap.cli.args import build_parser
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "--no-cache"])
    assert args.no_cache is True


def test_sarif_flag_in_cli_args():
    from archmap.cli.args import build_parser
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "--sarif"])
    assert args.sarif is True


def test_out_sarif_flag_in_cli_args():
    from archmap.cli.args import build_parser
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "--out-sarif", "out/my.sarif"])
    assert args.out_sarif == "out/my.sarif"
