from __future__ import annotations

import argparse

from archmap.cli.defaults import (
    DEFAULT_CYTOSCAPE_OUTPUT_PATH,
    DEFAULT_HOST,
    DEFAULT_JSON_OUTPUT_PATH,
    DEFAULT_MERMAID_OUTPUT_PATH,
    DEFAULT_PORT,
    DEFAULT_TOP_ITEMS,
)


def apply_default_command(args: argparse.Namespace) -> None:
    if args.command:
        return

    # Friendly behavior for double-clicking in a bundled executable.
    args.command = "serve"
    args.path = "."
    args.port = DEFAULT_PORT
    args.host = DEFAULT_HOST
    args.no_open = False
    args.format = "both"
    args.out = DEFAULT_JSON_OUTPUT_PATH
    args.out_mermaid = DEFAULT_MERMAID_OUTPUT_PATH
    args.out_cytoscape = DEFAULT_CYTOSCAPE_OUTPUT_PATH
    args.include_cytoscape = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archmap",
        description="ArchMAP - visualize architecture dependencies and risks",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="analyze a codebase")
    analyze_parser.add_argument("path", nargs="?", default=".")
    _add_export_arguments(analyze_parser, default_format="json")
    analyze_parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_ITEMS,
        help="number of top complexity/risk files shown in terminal summary",
    )
    analyze_parser.add_argument(
        "--fail-on-cycles",
        action="store_true",
        help="exit with code 2 when circular dependencies are detected",
    )
    analyze_parser.add_argument(
        "--fail-on-layer-violations",
        action="store_true",
        help="exit with code 2 when any layer violation is detected",
    )
    analyze_parser.add_argument(
        "--fail-on-god-modules",
        action="store_true",
        help="exit with code 2 when any god module is detected",
    )
    analyze_parser.add_argument(
        "--fail-on-dependency-explosions",
        action="store_true",
        help="exit with code 2 when any dependency explosion is detected",
    )
    analyze_parser.add_argument(
        "--fail-on-custom-rules",
        action="store_true",
        help="exit with code 2 when any custom architecture rule is violated",
    )
    analyze_parser.add_argument(
        "--fail-on-risks",
        action="store_true",
        help="exit with code 2 when cycles or any risk category is detected",
    )
    analyze_parser.add_argument(
        "--min-health",
        type=int,
        default=None,
        help="exit with code 2 when architecture health score falls below this threshold",
    )

    serve_parser = subparsers.add_parser("serve", help="serve the interactive graph UI")
    serve_parser.add_argument("path", nargs="?", default=".")
    _add_export_arguments(serve_parser, default_format="both")
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_parser.add_argument("--no-open", action="store_true")

    diff_parser = subparsers.add_parser("diff", help="compare architecture between two git refs")
    diff_parser.add_argument("base_ref")
    diff_parser.add_argument("head_ref")
    diff_parser.add_argument("--repo", default=".")
    diff_parser.add_argument("--json", action="store_true")

    history_parser = subparsers.add_parser(
        "history",
        help="inspect architecture evolution across git history",
    )
    history_parser.add_argument("--repo", default=".")
    history_parser.add_argument("--ref", default="HEAD")
    history_parser.add_argument("--limit", type=int, default=12)
    history_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("version", help="print tool version")
    return parser


def _add_export_arguments(parser: argparse.ArgumentParser, *, default_format: str) -> None:
    parser.add_argument("--format", choices=["json", "mermaid", "both"], default=default_format)
    parser.add_argument("--out", default=DEFAULT_JSON_OUTPUT_PATH)
    parser.add_argument("--out-mermaid", default=DEFAULT_MERMAID_OUTPUT_PATH)
    parser.add_argument("--out-cytoscape", default=DEFAULT_CYTOSCAPE_OUTPUT_PATH)
    parser.add_argument("--include-cytoscape", action="store_true")
