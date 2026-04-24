from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_check_injects_defaults_into_argv(tmp_path: Path) -> None:
    """archmap-check prepends default flags before forwarding to cli.main.main."""
    captured: list[list[str]] = []

    def fake_main() -> None:
        captured.append(list(sys.argv))

    with patch("archmap.cli.main.main", side_effect=fake_main):
        original_argv = sys.argv[:]
        sys.argv = ["archmap-check"]
        try:
            from archmap.cli import check
            importlib.reload(check)
            check.main()
        finally:
            sys.argv = original_argv

    assert len(captured) == 1
    argv = captured[0]
    assert "analyze" in argv
    assert "--quiet" in argv
    assert "--fail-on-cycles" in argv
    assert "--fail-on-custom-rules" in argv
    assert "--format" in argv
    assert "json" in argv


def test_check_preserves_extra_user_args(tmp_path: Path) -> None:
    """Extra args passed after script name are forwarded after defaults."""
    captured: list[list[str]] = []

    def fake_main() -> None:
        captured.append(list(sys.argv))

    with patch("archmap.cli.main.main", side_effect=fake_main):
        original_argv = sys.argv[:]
        sys.argv = ["archmap-check", "--fail-on-god-modules"]
        try:
            from archmap.cli import check
            importlib.reload(check)
            check.main()
        finally:
            sys.argv = original_argv

    argv = captured[0]
    assert "--fail-on-god-modules" in argv
    # defaults are still present
    assert "--fail-on-cycles" in argv


def test_pre_commit_hooks_yaml_exists() -> None:
    hooks_file = Path(".pre-commit-hooks.yaml")
    assert hooks_file.is_file(), ".pre-commit-hooks.yaml must exist at repo root"


def test_pre_commit_hooks_yaml_valid() -> None:
    import re
    hooks_file = Path(".pre-commit-hooks.yaml")
    content = hooks_file.read_text(encoding="utf-8")
    assert "archmap-check" in content
    assert "entry: archmap-check" in content
    assert "pass_filenames: false" in content
