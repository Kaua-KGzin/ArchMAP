from __future__ import annotations

import argparse
from typing import Any

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
        "--min-coverage",
        type=int,
        default=None,
        metavar="PCT",
        help=(
            "exit with code 2 when fewer than PCT percent of discovered source files "
            "were parsed into the graph "
            "(parse/decode failures and oversized files count against it)"
        ),
    )
    analyze_parser.add_argument(
        "--max-parse-failures",
        type=int,
        default=None,
        metavar="N",
        help="exit with code 2 when more than N source files fail to parse",
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
    _add_netscan_arguments(netscan_parser)

    expose_parser = subparsers.add_parser(
        "expose",
        help="correlate open network ports/services with your codebase's dependency graph",
        description=(
            "Scan a network target, analyze a codebase, and cross-reference the two: "
            "for each open port whose service has a known client library, find matching "
            "package dependencies in the code and surface their blast radius. "
            "Only scan networks and hosts you own or are explicitly authorized to test."
        ),
    )
    _add_netscan_arguments(expose_parser)
    expose_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project root to correlate against (default: current directory)",
    )

    memory_parser = subparsers.add_parser(
        "memory",
        help="generate a compact architecture digest for AI coding agents (Claude Code, etc.)",
        description=(
            "Renders the project's health, risks, cycles, and rule violations into a "
            "compact markdown snapshot (default: .archmap/memory.md) an AI coding agent "
            "can read at session start instead of re-exploring the codebase from "
            "scratch. Cheap to re-run: it reuses archmap's own analysis cache, so a "
            "no-op call after an unrelated edit is nearly instant. See docs/cli/memory.md "
            "for ready-to-paste Claude Code hook snippets that keep it fresh automatically."
        ),
    )
    memory_parser.add_argument("path", nargs="?", default=".")
    memory_parser.add_argument(
        "--out",
        default=None,
        help="output file path (default: <path>/.archmap/memory.md)",
    )
    memory_parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the digest to stdout instead of writing a file",
    )
    memory_parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the confirmation line (for use in hooks)",
    )
    memory_parser.add_argument(
        "--parallel",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable parallel file parsing for speedup",
    )

    _add_reverse_engineering_parsers(subparsers)

    subparsers.add_parser("version", help="print tool version")
    return parser


def _add_netscan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        help=(
            "host/IP, hostname, CIDR block, or range to scan "
            "(e.g. 192.168.1.10, 192.168.1.0/24, 192.168.1.1-50). "
            "Comma-separate multiple targets."
        ),
    )
    parser.add_argument(
        "--ports",
        default=None,
        metavar="SPEC",
        help="ports to scan, e.g. '22,80,443' or '1-1024' (default: top 20 common ports)",
    )
    parser.add_argument(
        "--top-ports",
        type=int,
        default=None,
        metavar="N",
        help="scan the N most common ports instead of an explicit --ports spec",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="only discover which hosts are up; skip port scanning",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="skip host discovery and port-scan every address in the target directly",
    )
    parser.add_argument(
        "--fingerprint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="grab service banners on open ports (default: on)",
    )
    parser.add_argument(
        "--use-nmap",
        dest="use_nmap",
        action="store_true",
        default=None,
        help=(
            "force the system nmap binary as the scan engine "
            "(default: used automatically when nmap is installed)"
        ),
    )
    parser.add_argument(
        "--no-nmap",
        dest="use_nmap",
        action="store_false",
        help="force the built-in Python scanner even if nmap is installed",
    )
    parser.add_argument(
        "--nmap-args",
        default=None,
        metavar="ARGS",
        help="extra raw arguments passed through to nmap (only when the nmap engine is used)",
    )
    parser.add_argument(
        "--os-detection",
        action="store_true",
        help="attempt OS fingerprinting via nmap -O (requires the nmap engine and root)",
    )
    parser.add_argument(
        "--scripts",
        action="store_true",
        help=(
            "run nmap's default scripts + version detection (-sC -sV) for deeper "
            "per-port analysis: page titles, TLS cert info, known misconfigurations, "
            "etc. (requires the nmap engine)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        metavar="SECS",
        help="per-connection timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=200,
        metavar="N",
        help="max concurrent connections for discovery/port scanning (default: 200)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="write the JSON report to file",
    )


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


_SEVERITY_CHOICES = ["info", "low", "medium", "high", "critical"]


def _add_reverse_engineering_parsers(subparsers: Any) -> None:
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="identify and analyze any file or folder: binaries, archives, databases, data",
        description=(
            "Static inspection of a file or directory. Executables (ELF, PE, Mach-O, "
            "WebAssembly) get headers, linked libraries, imports/exports, mitigation "
            "checks, entropy, and classified strings; archives, SQLite databases, JSON "
            "and CSV get a schema/content summary with red flags (zip-slip, setuid, "
            "decompression bombs). A directory is inventoried and its binaries' "
            "library links are mapped into a dependency graph. Nothing is executed."
        ),
    )
    inspect_parser.add_argument("path", help="file or directory to inspect")
    inspect_parser.add_argument("--json", action="store_true", help="print the full JSON report")
    inspect_parser.add_argument("--out", metavar="PATH", help="also write the JSON report here")
    inspect_parser.add_argument(
        "--no-strings", action="store_true", help="skip string extraction (faster)"
    )
    inspect_parser.add_argument(
        "--max-strings",
        type=int,
        default=100,
        metavar="N",
        help="maximum interesting strings to report for a file (default: 100)",
    )
    inspect_parser.add_argument(
        "--max-files",
        type=int,
        default=5000,
        metavar="N",
        help="maximum files to scan in a directory (default: 5000)",
    )
    inspect_parser.add_argument(
        "--fail-on",
        choices=_SEVERITY_CHOICES,
        default=None,
        metavar="SEVERITY",
        help="exit with code 2 when a finding at or above SEVERITY is reported",
    )

    hexdump_parser = subparsers.add_parser(
        "hexdump",
        help="canonical hex + ASCII dump of a byte range (like hexdump -C)",
    )
    hexdump_parser.add_argument("file")
    hexdump_parser.add_argument(
        "-s",
        "--offset",
        type=lambda text: int(text, 0),
        default=0,
        help="start offset; accepts 0x hex and negative values (from end of file)",
    )
    hexdump_parser.add_argument(
        "-n", "--length", type=lambda text: int(text, 0), default=256,
        help="number of bytes to dump (default: 256, max: 65536)",
    )
    hexdump_parser.add_argument(
        "-w", "--width", type=int, default=16, help="bytes per line (default: 16)"
    )

    strings_parser = subparsers.add_parser(
        "strings",
        help="extract printable ASCII/UTF-16 strings, optionally only the interesting ones",
    )
    strings_parser.add_argument("file")
    strings_parser.add_argument(
        "-n", "--min-length", type=int, default=4, help="minimum string length (default: 4)"
    )
    strings_parser.add_argument(
        "--encoding", choices=["ascii", "utf16le", "both"], default="both"
    )
    strings_parser.add_argument(
        "--interesting",
        action="store_true",
        help="only URLs, IPs, paths, registry keys, crypto/toolchain markers, secrets (redacted)",
    )
    strings_parser.add_argument(
        "--offsets", action="store_true", help="prefix each string with its offset"
    )
    strings_parser.add_argument("--limit", type=int, default=50_000, metavar="N")
    strings_parser.add_argument("--json", action="store_true")

    audit_parser = subparsers.add_parser(
        "audit",
        help="find committed secrets and risky AI-agent configuration (MCP, hooks, permissions)",
        description=(
            "Scans project text files for secrets (git-aware: committed secrets rank "
            "above local, untracked ones) and audits AI-agent configuration as attack "
            "surface: .mcp.json transports/unpinned packages/plaintext tokens, "
            ".claude/settings permissions and hooks, plugin hooks, and hidden Unicode "
            "in agent instruction files (CLAUDE.md, AGENTS.md, .cursorrules). Offline; "
            "secret values are always redacted."
        ),
    )
    audit_parser.add_argument("path", nargs="?", default=".")
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.add_argument("--out", metavar="PATH")
    audit_parser.add_argument(
        "--fail-on",
        choices=_SEVERITY_CHOICES,
        default=None,
        metavar="SEVERITY",
        help="exit with code 2 when a finding at or above SEVERITY is reported",
    )

    context_parser = subparsers.add_parser(
        "context",
        help="rank the files to read for a task, packed into a token budget (for AI agents)",
        description=(
            "Ranks project files for a free-text task with BM25 over identifier-aware "
            "tokens, spreads score to direct imports/dependents in the dependency "
            "graph, and packs the result into a token budget with matching lines. "
            "Same engine as the get_relevant_context MCP tool."
        ),
    )
    context_parser.add_argument(
        "task", help='what you are about to do, e.g. "fix retry in webhook"'
    )
    context_parser.add_argument("path", nargs="?", default=".")
    context_parser.add_argument(
        "--budget", type=int, default=8000, metavar="TOKENS",
        help="approximate tokens available for reading files (default: 8000)",
    )
    context_parser.add_argument("--max-files", type=int, default=15, metavar="N")
    context_parser.add_argument("--json", action="store_true")
    context_parser.add_argument(
        "--parallel", action=argparse.BooleanOptionalAction, default=True,
        help="enable parallel file parsing",
    )

    commands_parser = subparsers.add_parser(
        "commands",
        help="list every archmap command (--json: machine-readable catalog for AI agents)",
    )
    commands_parser.add_argument("--json", action="store_true")
