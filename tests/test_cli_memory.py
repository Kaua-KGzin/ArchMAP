from __future__ import annotations

import argparse
from pathlib import Path

from archmap.cli.commands import run_memory


def _make_args(
    path: str,
    *,
    out: str | None = None,
    print_only: bool = False,
    quiet: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        path=path, out=out, print_only=print_only, quiet=quiet, parallel=True
    )


def _write_small_project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("import os\n", encoding="utf-8")


def test_memory_writes_default_file(tmp_path: Path) -> None:
    _write_small_project(tmp_path)

    rc = run_memory(_make_args(str(tmp_path)))

    assert rc == 0
    memory_file = tmp_path / ".archmap" / "memory.md"
    assert memory_file.is_file()
    content = memory_file.read_text(encoding="utf-8")
    assert "# ArchMAP Project Memory" in content
    assert "Files: 1" in content


def test_memory_second_run_is_idempotent(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)
    run_memory(_make_args(str(tmp_path)))
    capsys.readouterr()

    rc = run_memory(_make_args(str(tmp_path)))

    assert rc == 0
    assert "already up to date" in capsys.readouterr().out


def test_memory_rewrites_after_project_change(tmp_path: Path) -> None:
    _write_small_project(tmp_path)
    run_memory(_make_args(str(tmp_path)))
    memory_file = tmp_path / ".archmap" / "memory.md"
    first_content = memory_file.read_text(encoding="utf-8")

    (tmp_path / "src" / "second.py").write_text("import sys\n", encoding="utf-8")
    run_memory(_make_args(str(tmp_path)))

    second_content = memory_file.read_text(encoding="utf-8")
    assert "Files: 2" in second_content
    assert first_content != second_content


def test_memory_print_only_does_not_write_file(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)

    rc = run_memory(_make_args(str(tmp_path), print_only=True))

    assert rc == 0
    assert not (tmp_path / ".archmap" / "memory.md").exists()
    out = capsys.readouterr().out
    assert "# ArchMAP Project Memory" in out


def test_memory_quiet_suppresses_confirmation(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)

    rc = run_memory(_make_args(str(tmp_path), quiet=True))

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_memory_custom_out_path(tmp_path: Path) -> None:
    _write_small_project(tmp_path)
    custom_out = tmp_path / "notes" / "digest.md"

    rc = run_memory(_make_args(str(tmp_path), out=str(custom_out)))

    assert rc == 0
    assert custom_out.is_file()
    assert not (tmp_path / ".archmap" / "memory.md").exists()


def test_memory_handles_analyze_errors(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does-not-exist"

    rc = run_memory(_make_args(str(missing)))

    assert rc == 1
    assert "does not exist" in capsys.readouterr().err
