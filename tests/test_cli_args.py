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
    assert args.top == DEFAULT_TOP_ITEMS
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
