from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
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
    print_human_insights,
    print_impact_analysis,
    print_improve_report,
    print_project_explanation,
    print_risk_report,
    print_simple_map,
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
from archmap.core.analyzer import (
    analyze_git_history,
    analyze_git_ref,
    diff_reports,
    generate_refactor_script,
    suggest_architecture,
)
from archmap.utils.file_utils import normalize_file_id

KNOWN_INIT_IGNORE_DIRS = {
    ".eggs",
    ".mypy_cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "out",
    "site",
    "target",
    "vendor",
    "venv",
}


def run_analyze(args: argparse.Namespace) -> int:
    quiet = getattr(args, "quiet", False)
    no_cache = getattr(args, "no_cache", False)
    sarif_path = _resolve_sarif_output(args)

    report = analyze_project(
        args.path, parallel=getattr(args, "parallel", None), use_cache=not no_cache
    )
    export_kwargs = {
        "report": report,
        "output_format": args.format,
        "json_output": args.out,
        "mermaid_output": args.out_mermaid,
        "cytoscape_output": args.out_cytoscape,
        "sarif_output": sarif_path,
        "include_cytoscape": args.include_cytoscape,
        "no_subgraphs": getattr(args, "no_subgraphs", False),
    }

    export_result = export_outputs(**export_kwargs)

    if not quiet:
        top_count = max(0, int(args.top))
        print_summary(report)
        if args.include_insights:
            print_human_insights(report)
        if args.include_explanation:
            print_project_explanation(report)
        if getattr(args, "impact", None):
            print_impact_analysis(report, args.impact)
        print_top_complexity(report, top_count)
        print_top_risks(report, top_count)
        print_export_summary(export_result)

    gate_failures = evaluate_quality_gates(report, args)
    if gate_failures:
        for failure in gate_failures:
            print(f"[gate] {failure}", file=sys.stderr)
        return 2

    if not quiet:
        print('[hint] Run "archmap serve <path>" to open the interactive graph.')
    return 0


def _resolve_sarif_output(args: argparse.Namespace) -> str | None:
    from archmap.cli.defaults import DEFAULT_SARIF_OUTPUT_PATH

    out_sarif = getattr(args, "out_sarif", None)
    include_sarif = getattr(args, "sarif", False)
    if out_sarif:
        return out_sarif
    if include_sarif:
        return DEFAULT_SARIF_OUTPUT_PATH
    return None


def run_serve(args: argparse.Namespace) -> int:
    no_cache = getattr(args, "no_cache", False)
    state = ReportState.from_path(
        args.path, parallel=getattr(args, "parallel", None), use_cache=not no_cache
    )
    export_kwargs = {
        "report": state.report,
        "output_format": args.format,
        "json_output": args.out,
        "mermaid_output": args.out_mermaid,
        "cytoscape_output": args.out_cytoscape,
        "sarif_output": _resolve_sarif_output(args),
        "include_cytoscape": args.include_cytoscape,
        "no_subgraphs": getattr(args, "no_subgraphs", False),
    }

    export_result = export_outputs(**export_kwargs)

    print_summary(state.report)
    print_human_insights(state.report)
    print_project_explanation(state.report)
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

    browser_opened = False
    if not args.no_open and can_open_browser(args.host):
        browser_opened = webbrowser.open(browser_url, new=2, autoraise=False)

    if getattr(args, "watch", False):
        watcher_thread = threading.Thread(
            target=_serve_watch_loop,
            args=(state,),
            daemon=True,
        )
        watcher_thread.start()

    print(f"[info] ArchMAP Service Map v{__version__}")
    print(f"[info] Analyzing: {state.path}")
    print(f"[info] Web UI available at {browser_url}")
    if bind_url != browser_url:
        print(f"[info] Listening on {bind_url}")
    if not browser_opened:
        print(f"[hint] Open {browser_url} in your browser to view the interactive graph.")
    print("[info] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] Shutting down server.")
    finally:
        server.server_close()
    return 0


def run_explain(args: argparse.Namespace) -> int:
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    suggestions = suggest_architecture(report, max_groups=max(2, int(args.max_groups)))
    payload = {
        "projectRoot": report.get("projectRoot"),
        "summary": report.get("metrics", {}),
        "architecture": report.get("architecture", {}),
        "insights": report.get("insights", {}),
        "explanation": report.get("explanation", {}),
        "simpleMap": suggestions.get("simpleMap", {}),
        "suggestions": suggestions.get("groups", []),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print_summary(report)
    print_human_insights(report)
    print_project_explanation(report)
    print_simple_map(suggestions.get("simpleMap", {}))
    return 0


def run_risk(args: argparse.Namespace) -> int:
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    risk_payload = _build_file_risk_payload(report, Path(args.path), args.target)
    if risk_payload is None:
        print(f"[error] File not found in analyzed project: {args.target}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(risk_payload, indent=2))
        return 0

    print_risk_report(risk_payload, max_impacted=max(0, int(args.max_impacted)))
    return 0


def run_improve(args: argparse.Namespace) -> int:
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    suggestions = suggest_architecture(report, max_groups=max(2, int(args.max_groups)))
    payload = {
        "projectRoot": report.get("projectRoot"),
        "summary": suggestions.get("summary"),
        "simpleMap": suggestions.get("simpleMap", {}),
        "groups": suggestions.get("groups", []),
        "moves": suggestions.get("moves", []),
        "suggestedLayout": suggestions.get("suggestedLayout", {}),
    }

    script_path = getattr(args, "out_script", None)
    if script_path:
        script_text = generate_refactor_script(suggestions)
        output_path = Path(script_path).resolve()
        output_path.write_text(script_text, encoding="utf-8")
        payload["scriptPath"] = str(output_path)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print_improve_report(suggestions)
    print_simple_map(suggestions.get("simpleMap", {}))
    if script_path:
        print(f"[info] Refactor helper script written to {payload['scriptPath']}")
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


def run_init(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    config_path = root / ".archmap.toml"

    if config_path.exists() and not args.force:
        print(
            f"[error] {config_path} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    ignore_dirs: list[str] = []
    layer_candidates: list[str] = []

    try:
        with os.scandir(root) as entries:
            for entry in sorted(entries, key=lambda item: item.name.lower()):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name in KNOWN_INIT_IGNORE_DIRS:
                    ignore_dirs.append(entry.name)
                    continue
                if not entry.name.startswith("."):
                    layer_candidates.append(entry.name)
    except OSError as exc:
        print(f"[error] Cannot scan {root}: {exc}", file=sys.stderr)
        return 1

    ignore_line = _render_ignore_dirs(ignore_dirs)
    layer_block = _render_layer_suggestions(layer_candidates)
    content = (
        "# Generated by `archmap init`\n"
        "# See https://github.com/Kaua-KGzin/ArchMAP for full documentation.\n\n"
        "[analysis]\n"
        "# Directories to skip during analysis.\n"
        f"{ignore_line}\n\n"
        "[architecture.rules]\n"
        "# Define allowed and forbidden dependency directions between layers.\n"
        '# forbid = ["ui -> database", "controller -> repository"]\n'
        '# allow  = ["controller -> service", "service -> repository"]\n\n'
        "[risks.layer_order]\n"
        f"{layer_block}\n"
    )

    if args.dry_run:
        print(content, end="")
        return 0

    config_path.write_text(content, encoding="utf-8")
    print(f"[ok] Created {config_path}")
    print('[hint] Run "archmap analyze ." to verify your configuration.')
    return 0


def run_watch(args: argparse.Namespace) -> int:
    path = Path(args.path).resolve()
    interval = getattr(args, "interval", 2.0)

    print(f"[info] Watching for changes in {path} (interval: {interval}s)")
    print("[info] Press Ctrl+C to stop.")

    last_mtimes = _get_project_mtimes(path)
    last_report = analyze_project(path, parallel=getattr(args, "parallel", True))
    print_summary(last_report)

    try:
        while True:
            time.sleep(interval)
            current_mtimes = _get_project_mtimes(path)
            if current_mtimes != last_mtimes:
                print(f"\n[watch] {time.strftime('%H:%M:%S')} Change detected. Re-analyzing...")
                new_report = analyze_project(path, parallel=getattr(args, "parallel", True))
                _print_watch_diff(last_report, new_report)
                last_mtimes = current_mtimes
                last_report = new_report
    except KeyboardInterrupt:
        print("\n[info] Stopped watching.")
    return 0


def _serve_watch_loop(state: ReportState) -> None:
    path = state.path
    last_mtimes = _get_project_mtimes(path)
    while True:
        time.sleep(2.0)
        try:
            current_mtimes = _get_project_mtimes(path)
            if current_mtimes != last_mtimes:
                print(f"[watch] {time.strftime('%H:%M:%S')} Change detected. Updating UI...")
                state.reanalyze()
                last_mtimes = current_mtimes
        except Exception as exc:  # noqa: BLE001
            print(f"[error] Watch re-analysis failed: {exc}")


def _render_ignore_dirs(ignore_dirs: list[str]) -> str:
    if not ignore_dirs:
        return "ignore_dirs = []"
    ignore_list = ", ".join(f'"{directory}"' for directory in ignore_dirs)
    return f"ignore_dirs = [{ignore_list}]"


def _render_layer_suggestions(layer_candidates: list[str]) -> str:
    if layer_candidates:
        suggestions = "\n".join(
            f"# {candidate} = {index + 1}"
            for index, candidate in enumerate(layer_candidates[:12])
        )
    else:
        suggestions = "# api = 1\n# core = 2\n# utils = 3"

    return (
        "# Assign an integer rank to each layer (lower = more foundational).\n"
        f"{suggestions}"
    )


def _build_file_risk_payload(
    report: dict,
    project_path: Path,
    target_path: str,
) -> dict | None:
    project_root = Path(report.get("projectRoot", project_path)).resolve()
    normalized_target = _normalize_target_id(project_root, target_path)
    node = next(
        (entry for entry in report.get("nodes", []) if entry.get("id") == normalized_target),
        None,
    )
    if not node or node.get("type") != "file":
        return None

    risk_index = {
        item["file"]: item
        for item in report.get("risks", {}).get("top_risk_files", [])
    }
    risk_item = risk_index.get(normalized_target, {})
    return {
        "file": normalized_target,
        "incoming": int(node.get("incoming", 0)),
        "outgoing": int(node.get("outgoing", 0)),
        "isCircular": bool(node.get("isCircular", False)),
        "impact": node.get("impact", {}),
        "riskScore": int(risk_item.get("riskScore", 0)),
        "signals": list(risk_item.get("signals", [])),
    }


def _normalize_target_id(project_root: Path, target_path: str) -> str:
    candidate = Path(target_path)
    if candidate.is_absolute():
        try:
            return normalize_file_id(candidate.resolve().relative_to(project_root).as_posix())
        except ValueError:
            return normalize_file_id(candidate.name)
    return normalize_file_id(target_path)


def _get_project_mtimes(path: Path) -> dict[str, float]:
    from archmap.utils.file_utils import discover_source_files

    files = discover_source_files(path)
    mtimes = {}
    for file_path in files:
        try:
            mtimes[str(file_path)] = file_path.stat().st_mtime
        except OSError:
            continue
    return mtimes


def _print_watch_diff(old: dict, new: dict) -> None:
    old_health = old.get("architecture", {}).get("health", {}).get("score", 0)
    new_health = new.get("architecture", {}).get("health", {}).get("score", 0)

    if old_health != new_health:
        delta = new_health - old_health
        sign = "+" if delta > 0 else ""
        print(f"  Health Score: {old_health/10:.1f} -> {new_health/10:.1f} ({sign}{delta/10:.1f})")

    old_cycles = len(old.get("cycles", []))
    new_cycles = len(new.get("cycles", []))
    if old_cycles != new_cycles:
        delta = new_cycles - old_cycles
        sign = "+" if delta > 0 else ""
        print(f"  Cycles: {old_cycles} -> {new_cycles} ({sign}{delta})")

    old_files = {node["id"] for node in old.get("nodes", []) if node.get("type") == "file"}
    new_files = {node["id"] for node in new.get("nodes", []) if node.get("type") == "file"}

    added = new_files - old_files
    removed = old_files - new_files
    if added:
        print(f"  Added: {len(added)} files")
    if removed:
        print(f"  Removed: {len(removed)} files")
