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
    args.no_subgraphs = False
    args.parallel = True
    args.sarif = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archmap",
        description="ArchMAP - visualize architecture dependencies and risks",
    )
    parser.add_argument(
        "--print-completion",
        choices=["bash", "zsh", "fish"],
        metavar="SHELL",
        help="Print shell completion setup command for SHELL and exit.",
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
        "--quiet", "-q",
        action="store_true",
        dest="quiet",
        help="suppress banner, insights, and hints — print only violations (useful in CI)",
    )
    analyze_parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="skip loading and saving cached analysis results",
    )
    analyze_parser.add_argument(
        "--min-resolution-rate",
        type=int,
        default=None,
        metavar="PCT",
        help="exit with code 2 when import resolution rate is below PCT percent (0-100)",
    )
    analyze_parser.add_argument(
        "--show-unresolved",
        type=int,
        default=0,
        nargs="?",
        const=20,
        metavar="N",
        help=(
            "print unresolved imports in the summary; "
            "N controls how many are shown (default 20 when flag is present)"
        ),
    )
    analyze_parser.add_argument(
        "--fail-on-budget-violations",
        action="store_true",
        help=(
            "exit with code 2 when any file exceeds coupling budgets "
            "(set via .archmap.toml [analysis.budgets] or --max-outgoing/incoming-per-file)"
        ),
    )
    analyze_parser.add_argument(
        "--max-outgoing-per-file",
        type=int,
        default=None,
        metavar="N",
        help="CLI override for max outgoing dependencies per file (overrides config file)",
    )
    analyze_parser.add_argument(
        "--max-incoming-per-file",
        type=int,
        default=None,
        metavar="N",
        help="CLI override for max incoming dependencies per file (overrides config file)",
    )
    analyze_parser.add_argument(
        "--ignore-external",
        action="store_true",
        help=(
            "exclude external package nodes and their edges from the output; "
            "useful for focusing the graph on internal structure only"
        ),
    )
    analyze_parser.add_argument(
        "--summary-format",
        choices=["text", "table", "markdown"],
        default="text",
        dest="summary_format",
        metavar="FMT",
        help="terminal summary output style: text (default), table, or markdown",
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

    diff_parser = subparsers.add_parser(
        "diff",
        help="compare architecture between two git refs or two JSON snapshots",
    )
    diff_parser.add_argument("base_ref", nargs="?", default=None)
    diff_parser.add_argument("head_ref", nargs="?", default=None)
    diff_parser.add_argument("--repo", default=".")
    diff_parser.add_argument("--json", action="store_true")
    diff_parser.add_argument(
        "--snapshot-a",
        metavar="PATH",
        help="compare two JSON snapshot files instead of git refs",
    )
    diff_parser.add_argument(
        "--snapshot-b",
        metavar="PATH",
        help="compare two JSON snapshot files instead of git refs",
    )

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
    init_parser.add_argument(
        "--from-analysis",
        action="store_true",
        help="analyze the project first and generate layer rules from the actual dependency graph",
    )

    trace_parser = subparsers.add_parser(
        "trace",
        help="trace all files reachable from an entrypoint through the dependency graph",
    )
    trace_parser.add_argument("entrypoint", help="entry file to trace from (relative path)")
    trace_parser.add_argument("path", nargs="?", default=".")
    trace_parser.add_argument("--json", action="store_true")
    trace_parser.add_argument(
        "--out", metavar="PATH", default=None, help="write JSON output to file"
    )
    trace_parser.add_argument(
        "--unreachable", action="store_true", help="also list unreachable files"
    )
    trace_parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="only include files reachable within N hops",
    )
    trace_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    advise_parser = subparsers.add_parser(
        "advise",
        help="get AI-powered architectural advice from an LLM",
    )
    advise_parser.add_argument("path", nargs="?", default=".")
    advise_parser.add_argument(
        "--provider",
        default="claude",
        choices=["claude", "openai", "ollama", "custom"],
        help="LLM provider (default: claude)",
    )
    advise_parser.add_argument(
        "--model",
        default=None,
        help="model name (e.g. claude-opus-4-7, gpt-4o, llama3)",
    )
    advise_parser.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help="API key (overrides ANTHROPIC_API_KEY / OPENAI_API_KEY env vars)",
    )
    advise_parser.add_argument(
        "--base-url",
        default=None,
        metavar="URL",
        help="custom base URL for OpenAI-compatible endpoints (e.g. Ollama, LM Studio)",
    )
    advise_parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        metavar="SECS",
        help="HTTP timeout in seconds (default: 90)",
    )
    advise_parser.add_argument("--json", action="store_true")
    advise_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    mcp_parser = subparsers.add_parser(
        "mcp",
        help="start an MCP server for AI assistant integration (Claude Code, Cursor, Windsurf)",
    )
    mcp_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project root to analyze (default: current directory)",
    )

    temporal_parser = subparsers.add_parser(
        "temporal",
        help="detect temporal coupling — files that frequently change together in git history",
    )
    temporal_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="git repository root to analyze (default: current directory)",
    )
    temporal_parser.add_argument(
        "--min-commits",
        type=int,
        default=2,
        metavar="N",
        help="minimum co-change count to include a pair (default: 2)",
    )
    temporal_parser.add_argument(
        "--top",
        type=int,
        default=20,
        metavar="N",
        help="number of top pairs to show (default: 20)",
    )
    temporal_parser.add_argument("--json", action="store_true")

    netscan_parser = subparsers.add_parser(
        "netscan",
        help="discover hosts and open ports on a network (nmap-style, works in Termux, no root)",
        description=(
            "Discover live hosts and scan open ports on a network. Pure Python by "
            "default (no root/dependencies needed — works in Termux), or delegate "
            "to the system nmap binary with --use-nmap. "
            "Only scan networks and hosts you own or are explicitly authorized to test."
        ),
    )
    netscan_parser.add_argument(
        "target",
        help=(
            "host/IP, hostname, CIDR block, or range to scan "
            "(e.g. 192.168.1.10, 192.168.1.0/24, 192.168.1.1-50). "
            "Comma-separate multiple targets."
        ),
    )
    netscan_parser.add_argument(
        "--ports",
        default=None,
        metavar="SPEC",
        help="ports to scan, e.g. '22,80,443' or '1-1024' (default: top 20 common ports)",
    )
    netscan_parser.add_argument(
        "--top-ports",
        type=int,
        default=None,
        metavar="N",
        help="scan the N most common ports instead of an explicit --ports spec",
    )
    netscan_parser.add_argument(
        "--discover-only",
        action="store_true",
        help="only discover which hosts are up; skip port scanning",
    )
    netscan_parser.add_argument(
        "--no-discover",
        action="store_true",
        help="skip host discovery and port-scan every address in the target directly",
    )
    netscan_parser.add_argument(
        "--fingerprint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="grab service banners on open ports (default: on)",
    )
    netscan_parser.add_argument(
        "--use-nmap",
        action="store_true",
        help="delegate scanning to the system nmap binary instead of the built-in scanner",
    )
    netscan_parser.add_argument(
        "--nmap-args",
        default=None,
        metavar="ARGS",
        help="extra raw arguments passed through to nmap (only with --use-nmap)",
    )
    netscan_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        metavar="SECS",
        help="per-connection timeout in seconds (default: 1.0)",
    )
    netscan_parser.add_argument(
        "--concurrency",
        type=int,
        default=200,
        metavar="N",
        help="max concurrent connections for discovery/port scanning (default: 200)",
    )
    netscan_parser.add_argument("--json", action="store_true")
    netscan_parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="write the JSON scan report to file",
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
        action="store_true",
        default=False,
        help="export a SARIF 2.1.0 report alongside the other outputs",
    )
    parser.add_argument(
        "--out-sarif",
        default=None,
        metavar="PATH",
        help="path for the SARIF 2.1.0 output file",
    )
