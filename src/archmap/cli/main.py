from __future__ import annotations

import sys

from archmap import __version__
from archmap.cli.defaults import DEFAULT_HOST, DEFAULT_JSON_OUTPUT_PATH, DEFAULT_MERMAID_OUTPUT_PATH, DEFAULT_PORT
from archmap.cli.args import apply_default_command as _apply_default_command
from archmap.cli.args import build_parser as _build_parser
from archmap.cli.commands import run_analyze as _run_analyze
from archmap.cli.commands import run_diff as _run_diff
from archmap.cli.commands import run_explain as _run_explain
from archmap.cli.commands import run_history as _run_history
from archmap.cli.commands import run_improve as _run_improve
from archmap.cli.commands import run_init as _run_init
from archmap.cli.commands import run_risk as _run_risk
from archmap.cli.commands import run_serve as _run_serve
from archmap.cli.commands import run_watch as _run_watch


def _print_banner() -> None:
    banner = rf"""
    ___          _      __  __   _   ___
   / _ \ _ _ ___| |_   |  \/  | /_\ | _ \
  | (_) | '_/ __| ' \  | |\/| |/ _ \|  _/
   \___/|_| \___|_||_| |_|  |_/_/ \_\_|

   ArchMAP Architectural Visualizer v{__version__}
   by Kaua-KGzin — Professional Analysis for Modern Codebases
    """
    print(banner)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, AttributeError):
            pass


def _resolve_command_handler(command: str | None):
    handlers = {
        "analyze": _run_analyze,
        "serve": _run_serve,
        "diff": _run_diff,
        "explain": _run_explain,
        "risk": _run_risk,
        "improve": _run_improve,
        "history": _run_history,
        "init": _run_init,
        "watch": _run_watch,
    }
    return handlers.get(command)


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    _apply_default_command(args)

    if args.command == "version":
        _print_banner()
        print(f"archmap {__version__}")
        return 0

    if sys.stdout.isatty():
        _print_banner()

    handler = _resolve_command_handler(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n[info] Interrupted.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        if getattr(sys, "frozen", False):
            input("\n[info] Press Enter to exit...")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
