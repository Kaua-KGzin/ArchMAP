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
from typing import Any

from archmap import __version__
from archmap.cli.defaults import DEFAULT_SARIF_OUTPUT_PATH, DEFAULT_TOP_ITEMS
from archmap.cli.reporting import (
    evaluate_quality_gates,
    export_outputs,
    print_advise_report,
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
    print_trace_report,
    print_unresolved_imports,
)
from archmap.cli.server import (
    ReportState,
    _is_loopback_host,
    browser_host,
    build_http_handler,
    can_open_browser,
    resolve_static_dir,
)
from archmap.core import analyze_project
from archmap.core.advisor import advise_architecture
from archmap.core.analyzer import (
    analyze_git_history,
    analyze_git_ref,
    diff_reports,
    generate_refactor_script,
    suggest_architecture,
    trace_reachability,
)
from archmap.utils.file_utils import normalize_file_id


def _resolve_sarif_path(args: argparse.Namespace) -> str | None:
    sarif_path = getattr(args, "out_sarif", None)
    if sarif_path:
        return sarif_path
    if getattr(args, "sarif", False):
        return DEFAULT_SARIF_OUTPUT_PATH
    return None


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


def _filter_external(report: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of report with external package nodes and their edges removed."""
    external_ids = {n["id"] for n in report.get("nodes", []) if n.get("type") == "package"}
    if not external_ids:
        return report
    nodes = [n for n in report["nodes"] if n["id"] not in external_ids]
    edges = [
        e for e in report["edges"]
        if e["source"] not in external_ids and e["target"] not in external_ids
    ]
    corrected_nodes = []
    for node in nodes:
        n = dict(node)
        n["outgoing"] = sum(1 for e in edges if e["source"] == n["id"])
        corrected_nodes.append(n)
    metrics = dict(report.get("metrics", {}))
    metrics["externalDependencies"] = 0
    metrics["totalDependencies"] = len(edges)
    return {**report, "nodes": corrected_nodes, "edges": edges, "metrics": metrics}


def run_analyze(args: argparse.Namespace) -> int:
    quiet = getattr(args, "quiet", False)
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    if getattr(args, "ignore_external", False):
        report = _filter_external(report)
    export_kwargs = {
        "report": report,
        "output_format": args.format,
        "json_output": args.out,
        "mermaid_output": args.out_mermaid,
        "cytoscape_output": args.out_cytoscape,
        "include_cytoscape": args.include_cytoscape,
        "no_subgraphs": getattr(args, "no_subgraphs", False),
        "sarif_output": _resolve_sarif_path(args),
    }

    export_result = export_outputs(
        **export_kwargs,
    )

    if not quiet:
        top_count = max(0, int(args.top))
        summary_format = getattr(args, "summary_format", "text") or "text"
        print_summary(report, summary_format=summary_format)
        show_unresolved = getattr(args, "show_unresolved", 0) or 0
        if show_unresolved:
            print_unresolved_imports(report, limit=int(show_unresolved))
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


def run_serve(args: argparse.Namespace) -> int:
    state = ReportState.from_path(args.path, parallel=getattr(args, "parallel", None))
    export_kwargs = {
        "report": state.report,
        "output_format": args.format,
        "json_output": args.out,
        "mermaid_output": args.out_mermaid,
        "cytoscape_output": args.out_cytoscape,
        "include_cytoscape": args.include_cytoscape,
        "no_subgraphs": getattr(args, "no_subgraphs", False),
        "sarif_output": _resolve_sarif_path(args),
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

    if not args.no_open and can_open_browser(args.host):
        webbrowser.open(browser_url, new=2, autoraise=False)

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
    if not _is_loopback_host(args.host):
        print(
            f"[warn] Server bound to {args.host}: reachable from other hosts on the "
            "network. Local-only endpoints (open file, switch project, advise) stay "
            "restricted to loopback, but anyone who can reach this port can read the "
            "dependency graph. Use --host 127.0.0.1 if that is not intended."
        )
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
    snapshot_a = getattr(args, "snapshot_a", None)
    snapshot_b = getattr(args, "snapshot_b", None)

    if snapshot_a or snapshot_b:
        if not snapshot_a or not snapshot_b:
            print("[error] Both --snapshot-a and --snapshot-b are required.", file=sys.stderr)
            return 1
        path_a = Path(snapshot_a).resolve()
        path_b = Path(snapshot_b).resolve()
        if not path_a.is_file():
            print(f"[error] Snapshot not found: {path_a}", file=sys.stderr)
            return 1
        if not path_b.is_file():
            print(f"[error] Snapshot not found: {path_b}", file=sys.stderr)
            return 1
        import json as _json
        base_report = _json.loads(path_a.read_text(encoding="utf-8"))
        head_report = _json.loads(path_b.read_text(encoding="utf-8"))
        base_label = path_a.name
        head_label = path_b.name
        base_report.setdefault("ref", base_label)
        head_report.setdefault("ref", head_label)
    else:
        if not args.base_ref or not args.head_ref:
            print(
                "[error] Provide two git refs (base head) or use --snapshot-a / --snapshot-b.",
                file=sys.stderr,
            )
            return 1
        repo_root = Path(args.repo).resolve()
        base_report = analyze_git_ref(repo_root, args.base_ref)
        base_report["ref"] = args.base_ref
        head_report = analyze_git_ref(repo_root, args.head_ref)
        head_report["ref"] = args.head_ref
        base_label = args.base_ref
        head_label = args.head_ref

    diff_result = diff_reports(base_report, head_report)
    print_diff_output(base_label, head_label, diff_result, as_json=args.json)
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

    if getattr(args, "from_analysis", False):
        print(f"[info] Analyzing {root} to derive layer rules...")
        analysis_report = analyze_project(root)
        blueprint = _derive_blueprint(analysis_report)
        layer_block = _render_layer_from_blueprint(blueprint["layer_order"])
        forbid_block = _render_forbid_hints(blueprint["forbidden_hints"])
        cycle_note = (
            f"# NOTE: {blueprint['cycle_count']} circular dependencies detected.\n"
            if blueprint["cycle_count"] > 0
            else ""
        )
        content = (
            "# Generated by `archmap init --from-analysis`\n"
            "# See https://github.com/Kaua-KGzin/ArchMAP for full documentation.\n\n"
            "[analysis]\n"
            f"{ignore_line}\n\n"
            "[architecture.rules]\n"
            f"{forbid_block}"
            '# allow  = ["controller -> service", "service -> repository"]\n\n'
            "[risks.layer_order]\n"
            f"# Derived from actual dependency direction (lower = more foundational).\n"
            f"{cycle_note}"
            f"{layer_block}\n"
        )
    else:
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


def run_trace(args: argparse.Namespace) -> int:
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    result = trace_reachability(
        report,
        args.entrypoint,
        max_depth=getattr(args, "max_depth", None),
    )

    out_path = getattr(args, "out", None)
    if out_path or args.json:
        import json as _json
        payload = _json.dumps(result, indent=2)
        if out_path:
            Path(out_path).write_text(payload, encoding="utf-8")
            print(f"[info] Trace written to {out_path}")
            return 0
        print(payload)
        return 0

    print_trace_report(result, show_unreachable=getattr(args, "unreachable", False))
    return 0 if "error" not in result else 1


def run_advise(args: argparse.Namespace) -> int:
    report = analyze_project(args.path, parallel=getattr(args, "parallel", None))
    print(f"[info] Sending analysis to {args.provider}...")

    result = advise_architecture(
        report,
        provider=args.provider,
        model=getattr(args, "model", None),
        api_key=getattr(args, "api_key", None),
        base_url=getattr(args, "base_url", None),
        timeout=getattr(args, "timeout", 90),
    )

    if args.json:
        import json as _json
        print(_json.dumps(result, indent=2))
        return 0

    print_advise_report(result)
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


def run_mcp(args: argparse.Namespace) -> int:
    from archmap.cli.mcp_server import run_mcp_server
    return run_mcp_server(getattr(args, "path", "."))


def run_temporal(args: argparse.Namespace) -> int:
    from archmap.core.analyzer.temporal_analyzer import analyze_temporal_coupling

    result = analyze_temporal_coupling(
        args.path,
        min_commits=getattr(args, "min_commits", 2),
        top=getattr(args, "top", 20),
    )

    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps(result, indent=2))
        return 0

    if "error" in result:
        print(f"[error] {result['error']}", file=sys.stderr)
        return 1

    pairs = result.get("pairs", [])
    print(
        f"\n  Temporal Coupling Analysis — {result['totalCommitsScanned']} commits scanned\n"
        f"  Showing top {len(pairs)} pairs (min co-changes: {result['minCommits']})\n"
    )
    if not pairs:
        print("  No significant temporal coupling detected.")
        return 0

    header = f"  {'File A':<40} {'File B':<40} {'Co-Changes':>10}  {'Strength':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for p in pairs:
        a = p["fileA"][:38]
        b = p["fileB"][:38]
        print(f"  {a:<40} {b:<40} {p['coChanges']:>10}  {p['couplingStrength']:>8.3f}")

    print(f"\n  Total pairs with min {result['minCommits']} co-changes: {result['totalPairs']}")
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


def _derive_blueprint(report: dict[str, Any]) -> dict[str, Any]:
    nodes = report.get("nodes", [])

    dir_incoming: dict[str, int] = {}
    dir_outgoing: dict[str, int] = {}
    dir_files: dict[str, int] = {}

    for node in nodes:
        if node.get("type") != "file":
            continue
        fid = str(node.get("id", ""))
        parts = fid.split("/")
        dirname = parts[0] if len(parts) > 1 and parts[0] else "."
        dir_files[dirname] = dir_files.get(dirname, 0) + 1
        dir_incoming[dirname] = dir_incoming.get(dirname, 0) + int(node.get("incoming", 0))
        dir_outgoing[dirname] = dir_outgoing.get(dirname, 0) + int(node.get("outgoing", 0))

    def _score(d: str) -> float:
        total = dir_incoming.get(d, 0) + dir_outgoing.get(d, 0)
        return dir_outgoing.get(d, 0) / total if total > 0 else 0.5

    dirs = [
        d
        for d in dir_files
        if d not in KNOWN_INIT_IGNORE_DIRS and not d.startswith(".")
    ]
    dirs.sort(key=_score)

    layer_order = {d: i + 1 for i, d in enumerate(dirs)}

    forbidden_hints: list[str] = []
    for v in report.get("risks", {}).get("layer_violations", [])[:5]:
        from_layer = v.get("fromLayer", "")
        to_layer = v.get("toLayer", "")
        if from_layer and to_layer:
            forbidden_hints.append(f"{from_layer} -> {to_layer}")

    return {
        "layer_order": layer_order,
        "forbidden_hints": list(dict.fromkeys(forbidden_hints)),
        "cycle_count": int(report.get("metrics", {}).get("circularDependencyCount", 0)),
    }


def _render_layer_from_blueprint(layer_order: dict[str, int]) -> str:
    if not layer_order:
        return "# api = 1\n# core = 2\n# utils = 3"
    return "\n".join(
        f"{name} = {rank}"
        for name, rank in sorted(layer_order.items(), key=lambda x: x[1])
    )


def _render_forbid_hints(hints: list[str]) -> str:
    if not hints:
        return '# forbid = ["ui -> database", "controller -> repository"]\n'
    items = ", ".join(f'"{h}"' for h in hints)
    return f"forbid = [{items}]\n"


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
    report: dict[str, Any],
    project_path: Path,
    target_path: str,
) -> dict[str, Any] | None:
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
