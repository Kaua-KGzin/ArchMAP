from __future__ import annotations

import argparse

from archmap.cli.defaults import (
    DEFAULT_CYTOSCAPE_OUTPUT_PATH,
    DEFAULT_HOST,
    DEFAULT_JSON_OUTPUT_PATH,
    DEFAULT_MERMAID_OUTPUT_PATH,
    DEFAULT_SARIF_OUTPUT_PATH,
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
    args.no_subgraphs = False
    args.parallel = True
    args.sarif = None


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
        "--impact",
        metavar="PATH",
        help="Simulate the architectural impact of changing this file.",
    )
    analyze_parser.add_argument(
        "--include-insights",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print human-oriented architectural insights",
    )
    analyze_parser.add_argument(
        "--include-explanation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print an automatic project explanation",
    )
    analyze_parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_ITEMS,
        help="number of top complexity/risk files shown in terminal summary",
    )
    analyze_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
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
    analyze_parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress banner, insights, and hints — print only violations (useful in CI)",
    )

    serve_parser = subparsers.add_parser("serve", help="serve the interactive graph UI")
    serve_parser.add_argument("path", nargs="?", default=".")
    _add_export_arguments(serve_parser, default_format="both")
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_parser.add_argument("--no-open", action="store_true")
    serve_parser.add_argument(
        "--watch",
        action="store_true",
        help="automatically reload graph in browser when files change",
    )
    serve_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="watch for file changes and re-run analysis automatically",
    )
    watch_parser.add_argument("path", nargs="?", default=".")
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="polling interval in seconds (default: 2.0)",
    )
    watch_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    explain_parser = subparsers.add_parser(
        "explain",
        help="summarize the project with a simple architecture view",
    )
    explain_parser.add_argument("path", nargs="?", default=".")
    explain_parser.add_argument("--json", action="store_true")
    explain_parser.add_argument(
        "--max-groups",
        type=int,
        default=8,
        help="maximum number of groups shown in the simple architecture map",
    )
    explain_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    risk_parser = subparsers.add_parser(
        "risk",
        help="inspect architectural risk and blast radius for one file",
    )
    risk_parser.add_argument("target", help="file path to inspect inside the analyzed project")
    risk_parser.add_argument("path", nargs="?", default=".")
    risk_parser.add_argument("--json", action="store_true")
    risk_parser.add_argument(
        "--max-impacted",
        type=int,
        default=15,
        help="maximum number of impacted files shown in terminal output",
    )
    risk_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    improve_parser = subparsers.add_parser(
        "improve",
        help="suggest a cleaner project structure automatically",
    )
    improve_parser.add_argument("path", nargs="?", default=".")
    improve_parser.add_argument("--json", action="store_true")
    improve_parser.add_argument(
        "--max-groups",
        type=int,
        default=8,
        help="maximum number of suggested architecture groups",
    )
    improve_parser.add_argument(
        "--out-script",
        help="write a refactor helper script with suggested move commands",
    )
    improve_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

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

    init_parser = subparsers.add_parser(
        "init",
        help="create a .archmap.toml configuration file in a project directory",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project root to initialise (default: current directory)",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the generated config to stdout without writing a file",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing .archmap.toml without prompting",
    )

    subparsers.add_parser("version", help="print tool version")
    return parser


def _add_export_arguments(parser: argparse.ArgumentParser, *, default_format: str) -> None:
    parser.add_argument("--format", choices=["json", "mermaid", "both"], default=default_format)
    parser.add_argument("--out", default=DEFAULT_JSON_OUTPUT_PATH)
    parser.add_argument("--out-mermaid", default=DEFAULT_MERMAID_OUTPUT_PATH)
    parser.add_argument("--out-cytoscape", default=DEFAULT_CYTOSCAPE_OUTPUT_PATH)
    parser.add_argument("--include-cytoscape", action="store_true")
    parser.add_argument(
        "--no-subgraphs",
        action="store_true",
        help="Disable subgraph grouping by layer in Mermaid output",
    )
    parser.add_argument(
        "--sarif",
        metavar="PATH",
        nargs="?",
        const=DEFAULT_SARIF_OUTPUT_PATH,
        default=None,
        help="Export results in SARIF 2.1.0 format (default path: %(const)s)",
    )
