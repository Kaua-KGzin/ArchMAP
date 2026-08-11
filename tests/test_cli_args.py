from __future__ import annotations

from argparse import Namespace

from archmap.cli import args as cli_args
from archmap.cli.defaults import (
    DEFAULT_CYTOSCAPE_OUTPUT_PATH,
    DEFAULT_HOST,
    DEFAULT_JSON_OUTPUT_PATH,
    DEFAULT_MERMAID_OUTPUT_PATH,
    DEFAULT_PORT,
    DEFAULT_TOP_ITEMS,
)


def test_apply_default_command_populates_serve_defaults() -> None:
    args = Namespace(command=None)

    cli_args.apply_default_command(args)

    assert args.command == "serve"
    assert args.path == "."
    assert args.port == DEFAULT_PORT
    assert args.host == DEFAULT_HOST
    assert args.no_open is False
    assert args.format == "both"
    assert args.out == DEFAULT_JSON_OUTPUT_PATH
    assert args.out_mermaid == DEFAULT_MERMAID_OUTPUT_PATH
    assert args.out_cytoscape == DEFAULT_CYTOSCAPE_OUTPUT_PATH
    assert args.include_cytoscape is False
    assert args.no_subgraphs is False
    assert args.parallel is True


def test_apply_default_command_preserves_explicit_command() -> None:
    args = Namespace(command="analyze", path="repo")

    cli_args.apply_default_command(args)

    assert args.command == "analyze"
    assert args.path == "repo"


def test_build_parser_sets_analyze_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["analyze", "sample"])

    assert args.command == "analyze"
    assert args.path == "sample"
    assert args.format == "json"
    assert args.out == DEFAULT_JSON_OUTPUT_PATH
    assert args.out_mermaid == DEFAULT_MERMAID_OUTPUT_PATH
    assert args.out_cytoscape == DEFAULT_CYTOSCAPE_OUTPUT_PATH
    assert args.include_cytoscape is False
    assert args.no_subgraphs is False
    assert args.include_insights is True
    assert args.include_explanation is True
    assert args.top == DEFAULT_TOP_ITEMS
    assert args.parallel is True
    assert args.fail_on_cycles is False
    assert args.fail_on_layer_violations is False
    assert args.fail_on_god_modules is False
    assert args.fail_on_dependency_explosions is False
    assert args.fail_on_custom_rules is False
    assert args.fail_on_risks is False
    assert args.min_health is None


def test_build_parser_sets_serve_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["serve", "sample"])

    assert args.command == "serve"
    assert args.path == "sample"
    assert args.format == "both"
    assert args.host == DEFAULT_HOST
    assert args.port == DEFAULT_PORT
    assert args.no_open is False


def test_build_parser_sets_diff_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["diff", "main", "feature"])

    assert args.command == "diff"
    assert args.base_ref == "main"
    assert args.head_ref == "feature"
    assert args.repo == "."
    assert args.json is False


def test_build_parser_sets_history_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["history"])

    assert args.command == "history"
    assert args.repo == "."
    assert args.ref == "HEAD"
    assert args.limit == 12
    assert args.json is False


def test_build_parser_sets_explain_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["explain", "sample"])

    assert args.command == "explain"
    assert args.path == "sample"
    assert args.json is False
    assert args.max_groups == 8
    assert args.parallel is True


def test_build_parser_sets_risk_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["risk", "src/auth.ts", "sample"])

    assert args.command == "risk"
    assert args.target == "src/auth.ts"
    assert args.path == "sample"
    assert args.json is False
    assert args.max_impacted == 15
    assert args.parallel is True


def test_build_parser_sets_improve_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["improve", "sample"])

    assert args.command == "improve"
    assert args.path == "sample"
    assert args.json is False
    assert args.max_groups == 8
    assert args.out_script is None
    assert args.parallel is True


def test_build_parser_sets_netscan_defaults() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(["netscan", "192.168.1.0/24"])

    assert args.command == "netscan"
    assert args.target == "192.168.1.0/24"
    assert args.ports is None
    assert args.top_ports is None
    assert args.discover_only is False
    assert args.no_discover is False
    assert args.fingerprint is True
    assert args.use_nmap is False
    assert args.nmap_args is None
    assert args.timeout == 1.0
    assert args.concurrency == 200
    assert args.json is False
    assert args.out is None


def test_build_parser_netscan_accepts_overrides() -> None:
    parser = cli_args.build_parser()

    args = parser.parse_args(
        [
            "netscan",
            "10.0.0.1",
            "--ports", "22,80",
            "--discover-only",
            "--no-fingerprint",
            "--use-nmap",
            "--nmap-args=-sV",
            "--timeout", "2.5",
            "--concurrency", "50",
            "--json",
            "--out", "report.json",
        ]
    )

    assert args.ports == "22,80"
    assert args.discover_only is True
    assert args.fingerprint is False
    assert args.use_nmap is True
    assert args.nmap_args == "-sV"
    assert args.timeout == 2.5
    assert args.concurrency == 50
    assert args.json is True
    assert args.out == "report.json"
