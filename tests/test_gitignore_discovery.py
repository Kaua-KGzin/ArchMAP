"""File discovery honours .gitignore (via git itself) when asked to."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from archmap.utils.file_utils import discover_source_files

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("out/\n*.gen.ts\n!keep.gen.ts\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("export {}")
    (tmp_path / "src" / "api.gen.ts").write_text("export {}")
    (tmp_path / "src" / "keep.gen.ts").write_text("export {}")
    (tmp_path / "out" / "deep").mkdir(parents=True)
    (tmp_path / "out" / "deep" / "bundle.js").write_text("x")
    return tmp_path


def _ids(root: Path, files: list[Path]) -> set[str]:
    return {f.relative_to(root).as_posix() for f in files}


def test_gitignored_files_and_dirs_are_skipped(tmp_path):
    root = _repo(tmp_path)
    found = discover_source_files(root, respect_gitignore=True)
    assert _ids(root, found) == {"src/app.ts", "src/keep.gen.ts"}


def test_gitignored_dirs_are_pruned_not_walked(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    visited: list[str] = []
    real = os.scandir

    def spy(path="."):
        visited.append(os.fspath(path).replace("\\", "/"))
        return real(path)

    monkeypatch.setattr(os, "scandir", spy)
    discover_source_files(root, respect_gitignore=True)
    assert any(v.endswith("/src") for v in visited)
    assert not any("/out" in v for v in visited)


def test_tracked_file_matching_gitignore_is_kept(tmp_path):
    root = _repo(tmp_path)
    _git(root, "add", "-f", "src/api.gen.ts")
    found = discover_source_files(root, respect_gitignore=True)
    assert "src/api.gen.ts" in _ids(root, found)


def test_respect_gitignore_off_keeps_previous_behaviour(tmp_path):
    root = _repo(tmp_path)
    found = discover_source_files(root)
    assert _ids(root, found) == {
        "src/app.ts", "src/api.gen.ts", "src/keep.gen.ts", "out/deep/bundle.js",
    }


def test_subdirectory_of_a_repo_uses_paths_relative_to_it(tmp_path):
    root = _repo(tmp_path)
    found = discover_source_files(root / "src", respect_gitignore=True)
    assert _ids(root / "src", found) == {"app.ts", "keep.gen.ts"}


def test_outside_a_git_repo_nothing_is_filtered(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    (tmp_path / "a.ts").write_text("export {}")
    (tmp_path / ".gitignore").write_text("a.ts\n")
    assert _ids(tmp_path, discover_source_files(tmp_path, respect_gitignore=True)) == {"a.ts"}


def test_analysis_respects_gitignore_by_default_and_can_opt_out(tmp_path):
    from archmap.config import load_project_config
    from archmap.core.parser import parse_project

    root = _repo(tmp_path)
    ids = {f["id"] for f in parse_project(root)["parsedFiles"]}
    assert ids == {"src/app.ts", "src/keep.gen.ts"}

    (root / ".archmap.toml").write_text("[analysis]\nrespect_gitignore = false\n")
    config = load_project_config(root)
    assert config["analysis"]["respect_gitignore"] is False
    ids = {f["id"] for f in parse_project(root, config=config)["parsedFiles"]}
    assert "out/deep/bundle.js" in ids
