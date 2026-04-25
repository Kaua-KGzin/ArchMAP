"""Entry point for the `archmap-check` pre-commit hook.

Wraps `archmap analyze` with sensible defaults for CI / pre-commit usage:
- --quiet (suppress banner and hints)
- --fail-on-cycles (default: true)
- --fail-on-custom-rules (default: true)
- --format json (no interactive output)
"""

from __future__ import annotations

import sys


def main() -> None:
    from archmap.cli import main as cli_main

    defaults = [
        "analyze",
        ".",
        "--quiet",
        "--fail-on-cycles",
        "--fail-on-custom-rules",
        "--format",
        "json",
    ]

    # Preserve any extra args the user passes via pre-commit args: [...]
    extra = sys.argv[1:]
    sys.argv = [sys.argv[0]] + defaults + extra
    cli_main.main()
