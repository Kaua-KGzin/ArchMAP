from __future__ import annotations

import sys

from archmap import __version__
from archmap.cli import defaults as _defaults
from archmap.cli.args import (
    apply_default_command as _apply_default_command,
)
from archmap.cli.args import (
    build_parser as _build_parser,
)
from archmap.cli.commands import (
    run_analyze as _run_analyze,
)
from archmap.cli.commands import (
    run_diff as _run_diff,
)
from archmap.cli.commands import (
    run_history as _run_history,
)
from archmap.cli.commands import (
    run_serve as _run_serve,
)

DEFAULT_JSON_OUTPUT_PATH = _defaults.DEFAULT_JSON_OUTPUT_PATH
DEFAULT_MERMAID_OUTPUT_PATH = _defaults.DEFAULT_MERMAID_OUTPUT_PATH
DEFAULT_CYTOSCAPE_OUTPUT_PATH = _defaults.DEFAULT_CYTOSCAPE_OUTPUT_PATH
DEFAULT_PORT = _defaults.DEFAULT_PORT
DEFAULT_HOST = _defaults.DEFAULT_HOST
DEFAULT_TOP_ITEMS = _defaults.DEFAULT_TOP_ITEMS


def _print_banner() -> None:
    banner = rf"""
    ___          _      __  __   _   ___
   / _ \ _ _ ___| |_   |  \/  | /_\ | _ \\
  | (_) | '_/ __| ' \  | |\/| |/ _ \|  _/
   \___/|_| \___|_||_| |_|  |_/_/ \_\_|

   ArchMAP Architectural Visualizer v{__version__}
   Professional Analysis for Modern Codebases
   by Kaua-KGzin
    """
    print(banner)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _apply_default_command(args)

    _print_banner()
    try:
        if args.command == "version":
            return _run_version()

        handler = _resolve_command_handler(args.command)
        if handler is None:
            parser.print_help()
            return 1

        return handler(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        if getattr(sys, "frozen", False):
            input("\n[info] Press Enter to exit...")
        return 1


def _resolve_command_handler(command: str | None):
    handlers = {
        "analyze": _run_analyze,
        "serve": _run_serve,
        "diff": _run_diff,
        "history": _run_history,
    }
    return handlers.get(command)


def _run_version() -> int:
    print(f"archmap {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
