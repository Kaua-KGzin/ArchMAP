from __future__ import annotations

import argparse
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from archmap import __version__
from archmap.cli.defaults import DEFAULT_TOP_ITEMS
from archmap.cli.reporting import (
    evaluate_quality_gates,
    export_outputs,
    print_diff_output,
    print_export_summary,
    print_history_output,
    print_summary,
    print_top_complexity,
    print_top_risks,
)
from archmap.cli.server import (
    ReportState,
    browser_host,
    build_http_handler,
    can_open_browser,
    resolve_static_dir,
)
from archmap.core import analyze_project
from archmap.core.analyzer import analyze_git_history, analyze_git_ref, diff_reports


def run_analyze(args: argparse.Namespace) -> int:
    report = analyze_project(args.path)
    export_result = export_outputs(
        report=report,
        output_format=args.format,
        json_output=args.out,
        mermaid_output=args.out_mermaid,
        cytoscape_output=args.out_cytoscape,
        include_cytoscape=args.include_cytoscape,
    )

    top_count = max(0, int(args.top))
    print_summary(report)
    print_top_complexity(report, top_count)
    print_top_risks(report, top_count)
    print_export_summary(export_result)

    gate_failures = evaluate_quality_gates(report, args)
    if gate_failures:
        for failure in gate_failures:
            print(f"[gate] {failure}", file=sys.stderr)
        return 2

    print('[hint] Run "archmap serve <path>" to open the interactive graph.')
    return 0


def run_serve(args: argparse.Namespace) -> int:
    state = ReportState.from_path(args.path)
    export_result = export_outputs(
        report=state.report,
        output_format=args.format,
        json_output=args.out,
        mermaid_output=args.out_mermaid,
        cytoscape_output=args.out_cytoscape,
        include_cytoscape=args.include_cytoscape,
    )

    print_summary(state.report)
    print_top_complexity(state.report, DEFAULT_TOP_ITEMS)
    print_top_risks(state.report, DEFAULT_TOP_ITEMS)
    print_export_summary(export_result)

    static_dir = resolve_static_dir()
    if not static_dir.exists():
        raise RuntimeError(f"Web UI static directory not found: {static_dir}")

    handler = build_http_handler(state, static_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    host_for_browser = browser_host(args.host)
    browser_url = f"http://{host_for_browser}:{args.port}"
    bind_url = f"http://{args.host}:{args.port}"

    if not args.no_open and can_open_browser(args.host):
        webbrowser.open(browser_url, new=2, autoraise=False)

    print(f"[info] ArchMAP Service Map v{__version__}")
    print(f"[info] Analyzing: {state.path}")
    print(f"[info] Web UI available at {browser_url}")
    if bind_url != browser_url:
        print(f"[info] Listening on {bind_url}")
    print("[info] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] Shutting down server.")
    finally:
        server.server_close()
    return 0


def run_diff(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    base_report = analyze_git_ref(repo_root, args.base_ref)
    base_report["ref"] = args.base_ref
    head_report = analyze_git_ref(repo_root, args.head_ref)
    head_report["ref"] = args.head_ref

    diff_result = diff_reports(base_report, head_report)
    print_diff_output(args.base_ref, args.head_ref, diff_result, as_json=args.json)
    return 0


def run_history(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    history = analyze_git_history(repo_root, ref=args.ref, limit=args.limit)
    print_history_output(history, as_json=args.json)
    return 0
