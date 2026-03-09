from __future__ import annotations

import argparse
import importlib.resources
import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from archmap import __version__
from archmap.core import analyze_project
from archmap.core.analyzer import analyze_git_ref, diff_reports
from archmap.exporters import (
    export_graph_as_cytoscape,
    export_graph_as_json,
    export_graph_as_mermaid,
)

DEFAULT_JSON_OUTPUT_PATH = ".codeatlas/graph.json"
DEFAULT_MERMAID_OUTPUT_PATH = ".codeatlas/graph.mmd"
DEFAULT_CYTOSCAPE_OUTPUT_PATH = ".codeatlas/graph-cytoscape.json"
DEFAULT_PORT = 3000


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "version":
            print(f"archmap {__version__}")
            return 0
        if args.command == "analyze":
            return _run_analyze(args)
        if args.command == "serve":
            return _run_serve(args)
        if args.command == "diff":
            return _run_diff(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archmap",
        description="ArchMAP - visualize architecture dependencies and risks",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="analyze a codebase")
    analyze_parser.add_argument("path", nargs="?", default=".")
    analyze_parser.add_argument("--format", choices=["json", "mermaid", "both"], default="json")
    analyze_parser.add_argument("--out", default=DEFAULT_JSON_OUTPUT_PATH)
    analyze_parser.add_argument("--out-mermaid", default=DEFAULT_MERMAID_OUTPUT_PATH)
    analyze_parser.add_argument("--out-cytoscape", default=DEFAULT_CYTOSCAPE_OUTPUT_PATH)
    analyze_parser.add_argument("--include-cytoscape", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="serve the interactive graph UI")
    serve_parser.add_argument("path", nargs="?", default=".")
    serve_parser.add_argument("--format", choices=["json", "mermaid", "both"], default="both")
    serve_parser.add_argument("--out", default=DEFAULT_JSON_OUTPUT_PATH)
    serve_parser.add_argument("--out-mermaid", default=DEFAULT_MERMAID_OUTPUT_PATH)
    serve_parser.add_argument("--out-cytoscape", default=DEFAULT_CYTOSCAPE_OUTPUT_PATH)
    serve_parser.add_argument("--include-cytoscape", action="store_true")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_parser.add_argument("--no-open", action="store_true")

    diff_parser = subparsers.add_parser("diff", help="compare architecture between two git refs")
    diff_parser.add_argument("base_ref")
    diff_parser.add_argument("head_ref")
    diff_parser.add_argument("--repo", default=".")
    diff_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("version", help="print tool version")
    return parser


def _run_analyze(args: argparse.Namespace) -> int:
    report = analyze_project(args.path)
    export_result = _export_outputs(
        report=report,
        output_format=args.format,
        json_output=args.out,
        mermaid_output=args.out_mermaid,
        cytoscape_output=args.out_cytoscape,
        include_cytoscape=args.include_cytoscape,
    )

    _print_summary(report)
    _print_top_complexity(report)
    _print_top_risks(report)
    _print_export_summary(export_result)
    print('[hint] Run "archmap serve <path>" to open the interactive graph.')
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    report = analyze_project(args.path)
    export_result = _export_outputs(
        report=report,
        output_format=args.format,
        json_output=args.out,
        mermaid_output=args.out_mermaid,
        cytoscape_output=args.out_cytoscape,
        include_cytoscape=args.include_cytoscape,
    )

    _print_summary(report)
    _print_top_complexity(report)
    _print_top_risks(report)
    _print_export_summary(export_result)

    static_dir = _resolve_static_dir()
    if not static_dir.exists():
        raise RuntimeError(f"Web UI static directory not found: {static_dir}")

    url = f"http://localhost:{args.port}"
    if not args.no_open:
        webbrowser.open(url, new=2, autoraise=False)

    handler = _build_http_handler(report, static_dir)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"[info] Web UI available at {url}")
    print("[info] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] Shutting down server.")
    finally:
        server.server_close()
    return 0


def _run_diff(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    base_report = analyze_git_ref(repo_root, args.base_ref)
    base_report["ref"] = args.base_ref
    head_report = analyze_git_ref(repo_root, args.head_ref)
    head_report["ref"] = args.head_ref

    diff_result = diff_reports(base_report, head_report)

    if args.json:
        print(json.dumps(diff_result, indent=2))
        return 0

    edge_delta = diff_result["edges"]["delta"]
    cycle_delta = diff_result["cycles"]["delta"]
    complexity_delta_percent = diff_result["complexity"]["deltaPercent"]

    print(f"Comparing {args.base_ref} -> {args.head_ref}")
    print(f"{_signed(edge_delta)} dependencies")
    print(f"{_signed(cycle_delta)} circular dependencies")
    print(f"complexity {_signed_float(complexity_delta_percent)}%")

    risk_summary = diff_result["riskSummary"]
    print(f"{_signed(risk_summary['layerViolationsDelta'])} layer violations")
    print(f"{_signed(risk_summary['godModulesDelta'])} god modules")
    print(f"{_signed(risk_summary['dependencyExplosionsDelta'])} dependency explosions")
    return 0


def _export_outputs(
    *,
    report: dict,
    output_format: str,
    json_output: str,
    mermaid_output: str,
    cytoscape_output: str,
    include_cytoscape: bool,
) -> dict:
    result = {"jsonPath": None, "mermaidPath": None, "cytoscapePath": None}

    if output_format in {"json", "both"}:
        result["jsonPath"] = str(export_graph_as_json(report, json_output))
    if output_format in {"mermaid", "both"}:
        result["mermaidPath"] = str(export_graph_as_mermaid(report, mermaid_output))
    if include_cytoscape:
        result["cytoscapePath"] = str(export_graph_as_cytoscape(report, cytoscape_output))

    return result


def _print_summary(report: dict) -> None:
    metrics = report["metrics"]
    print(f"[ok] {metrics['filesAnalyzed']} files analyzed")
    print(f"[ok] {metrics['totalDependencies']} dependencies detected")
    print(f"[ok] {metrics['circularDependencyCount']} circular dependencies detected")


def _print_top_complexity(report: dict) -> None:
    top_complexity = report["metrics"]["complexity"][:5]
    if not top_complexity:
        return

    print("Top complexity (imports):")
    for item in top_complexity:
        score = round(float(item["score"]) * 100)
        print(f"  - {item['file']}: {item['imports']} imports ({score}% score)")


def _print_top_risks(report: dict) -> None:
    top_risks = report.get("risks", {}).get("top_risk_files", [])[:5]
    if not top_risks:
        return

    print("Top risk files:")
    for item in top_risks:
        signals = ", ".join(item.get("signals", [])) or "none"
        print(f"  - {item['file']}: score {item['riskScore']} ({signals})")


def _print_export_summary(export_result: dict) -> None:
    if export_result["jsonPath"]:
        print(f"[info] JSON report exported to {export_result['jsonPath']}")
    if export_result["mermaidPath"]:
        print(f"[info] Mermaid graph exported to {export_result['mermaidPath']}")
    if export_result["cytoscapePath"]:
        print(f"[info] Cytoscape data exported to {export_result['cytoscapePath']}")


def _resolve_static_dir() -> Path:
    # PyInstaller frozen bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "web-ui" / "static"

    # Installed wheel: static files are bundled inside the archmap package
    try:
        pkg_ref = importlib.resources.files("archmap") / "web-ui" / "static"
        pkg_path = Path(str(pkg_ref))
        if pkg_path.is_dir():
            return pkg_path
    except (TypeError, AttributeError):
        pass

    # Source-checkout fallback: repo_root/web-ui/static
    return Path(__file__).resolve().parents[3] / "web-ui" / "static"


def _build_http_handler(report: dict, static_dir: Path) -> type[SimpleHTTPRequestHandler]:
    report_bytes = json.dumps(report).encode("utf-8")
    health_bytes = b'{"status":"ok"}'

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def do_GET(self):  # noqa: N802
            if self.path == "/api/graph":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(report_bytes)))
                self.end_headers()
                self.wfile.write(report_bytes)
                return

            if self.path == "/api/health":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(health_bytes)))
                self.end_headers()
                self.wfile.write(health_bytes)
                return

            if self.path == "/":
                self.path = "/index.html"

            super().do_GET()

        def log_message(self, _format: str, *args) -> None:
            return

    return Handler


def _signed(value: int) -> str:
    return f"{value:+d}"


def _signed_float(value: float) -> str:
    return f"{value:+.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
