from __future__ import annotations

import argparse
import importlib.resources
import json
import sys
import webbrowser
from dataclasses import dataclass
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
DEFAULT_HOST = "0.0.0.0"
DEFAULT_TOP_ITEMS = 5


def _print_banner() -> None:
    banner = rf"""
    ___          _      __  __   _   ___
   / _ \ _ _ ___| |_   |  \/  | /_\ | _ \\
  | (_) | '_/ __| ' \  | |\/| |/ _ \|  _/
   \___/|_| \___|_||_| |_|  |_/_/ \_\_|

   ArchMAP Architectural Visualizer v{__version__}
   Professional Analysis for Modern Codebases
    """
    print(banner)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _apply_default_command(args)

    _print_banner()
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
        if getattr(sys, "frozen", False):
            input("\n[info] Press Enter to exit...")
        return 1

    parser.print_help()
    return 1


def _apply_default_command(args: argparse.Namespace) -> None:
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
        "--fail-on-risks",
        action="store_true",
        help="exit with code 2 when cycles or any risk category is detected",
    )

    serve_parser = subparsers.add_parser("serve", help="serve the interactive graph UI")
    serve_parser.add_argument("path", nargs="?", default=".")
    serve_parser.add_argument("--format", choices=["json", "mermaid", "both"], default="both")
    serve_parser.add_argument("--out", default=DEFAULT_JSON_OUTPUT_PATH)
    serve_parser.add_argument("--out-mermaid", default=DEFAULT_MERMAID_OUTPUT_PATH)
    serve_parser.add_argument("--out-cytoscape", default=DEFAULT_CYTOSCAPE_OUTPUT_PATH)
    serve_parser.add_argument("--include-cytoscape", action="store_true")
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
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

    top_count = max(0, int(args.top))
    _print_summary(report)
    _print_top_complexity(report, top_count)
    _print_top_risks(report, top_count)
    _print_export_summary(export_result)

    gate_failures = _evaluate_quality_gates(report, args)
    if gate_failures:
        for failure in gate_failures:
            print(f"[gate] {failure}", file=sys.stderr)
        return 2

    print('[hint] Run "archmap serve <path>" to open the interactive graph.')
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    state = ReportState.from_path(args.path)
    export_result = _export_outputs(
        report=state.report,
        output_format=args.format,
        json_output=args.out,
        mermaid_output=args.out_mermaid,
        cytoscape_output=args.out_cytoscape,
        include_cytoscape=args.include_cytoscape,
    )

    _print_summary(state.report)
    _print_top_complexity(state.report, DEFAULT_TOP_ITEMS)
    _print_top_risks(state.report, DEFAULT_TOP_ITEMS)
    _print_export_summary(export_result)

    static_dir = _resolve_static_dir()
    if not static_dir.exists():
        raise RuntimeError(f"Web UI static directory not found: {static_dir}")

    handler = _build_http_handler(state, static_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    browser_host = _browser_host(args.host)
    browser_url = f"http://{browser_host}:{args.port}"
    bind_url = f"http://{args.host}:{args.port}"

    if not args.no_open and _can_open_browser(args.host):
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


@dataclass
class ReportState:
    path: Path
    report: dict

    @classmethod
    def from_path(cls, path: str | Path) -> ReportState:
        resolved = Path(path).resolve()
        return cls(path=resolved, report=analyze_project(resolved))

    def set_path(self, new_path: Path) -> None:
        self.path = new_path.resolve()
        self.reanalyze()

    def reanalyze(self) -> None:
        self.report = analyze_project(self.path)


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


def _print_top_complexity(report: dict, limit: int) -> None:
    if limit <= 0:
        return

    top_complexity = report["metrics"]["complexity"][:limit]
    if not top_complexity:
        return

    print("Top complexity (imports):")
    for item in top_complexity:
        score = round(float(item["score"]) * 100)
        print(f"  - {item['file']}: {item['imports']} imports ({score}% score)")


def _print_top_risks(report: dict, limit: int) -> None:
    if limit <= 0:
        return

    top_risks = report.get("risks", {}).get("top_risk_files", [])[:limit]
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


def _evaluate_quality_gates(report: dict, args: argparse.Namespace) -> list[str]:
    metrics = report.get("metrics", {})
    risks = report.get("risks", {})

    cycle_count = int(metrics.get("circularDependencyCount", 0))
    layer_count = len(risks.get("layer_violations", []))
    god_count = len(risks.get("god_modules", []))
    explosion_count = len(risks.get("dependency_explosions", []))

    failures: list[str] = []
    if args.fail_on_cycles and cycle_count > 0:
        failures.append(f"cycle gate failed: {cycle_count} circular dependencies found")
    if args.fail_on_layer_violations and layer_count > 0:
        failures.append(f"layer gate failed: {layer_count} layer violations found")
    if args.fail_on_god_modules and god_count > 0:
        failures.append(f"god-module gate failed: {god_count} god modules found")
    if args.fail_on_dependency_explosions and explosion_count > 0:
        failures.append(
            f"dependency-explosion gate failed: {explosion_count} dependency explosions found"
        )
    if args.fail_on_risks and (
        cycle_count > 0 or layer_count > 0 or god_count > 0 or explosion_count > 0
    ):
        failures.append(
            "risk gate failed: detected cycles/layer violations/god modules/dependency explosions"
        )

    return failures


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

    # Source-checkout fallback: src/archmap/web-ui/static
    return Path(__file__).resolve().parents[1] / "web-ui" / "static"


def _build_http_handler(state: ReportState, static_dir: Path) -> type[SimpleHTTPRequestHandler]:
    health_payload = {"status": "ok"}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def do_POST(self):  # noqa: N802
            if self.path == "/api/open":
                self._handle_open_project()
                return
            if self.path == "/api/reanalyze":
                self._handle_reanalyze()
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_GET(self):  # noqa: N802
            if self.path == "/api/graph":
                self._write_json(HTTPStatus.OK, state.report)
                return

            if self.path == "/api/project":
                self._write_json(HTTPStatus.OK, {"path": str(state.path)})
                return

            if self.path == "/api/health":
                self._write_json(HTTPStatus.OK, health_payload)
                return

            if self.path == "/":
                self.path = "/index.html"

            super().do_GET()

        def _handle_open_project(self) -> None:
            new_path = self._pick_directory()
            if not new_path:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            try:
                state.set_path(new_path)
            except Exception as exc:  # noqa: BLE001
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(
                HTTPStatus.OK,
                {"status": "success", "path": str(new_path.resolve())},
            )

        def _handle_reanalyze(self) -> None:
            try:
                state.reanalyze()
            except Exception as exc:  # noqa: BLE001
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(HTTPStatus.OK, {"status": "success", "path": str(state.path)})

        def _write_json(self, status: HTTPStatus, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _pick_directory(self) -> Path | None:
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                directory = filedialog.askdirectory(title="ArchMAP - Select Project Folder")
                root.destroy()
                return Path(directory) if directory else None
            except Exception:
                return None

        def log_message(self, _format: str, *args) -> None:
            return

    return Handler


def _can_open_browser(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::", "::1"}


def _browser_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "localhost"
    return host


def _signed(value: int) -> str:
    return f"{value:+d}"


def _signed_float(value: float) -> str:
    return f"{value:+.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
