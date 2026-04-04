from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from archmap.utils.file_utils import first_segment, normalize_file_id

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def make_file_node() -> Callable[..., dict]:
    def _make(
        file_id: str,
        *,
        incoming: int = 0,
        outgoing: int = 0,
        language: str = "python",
    ) -> dict:
        normalized = normalize_file_id(file_id)
        return {
            "id": normalized,
            "label": normalized,
            "type": "file",
            "language": language,
            "folder": first_segment(normalized),
            "incoming": incoming,
            "outgoing": outgoing,
            "isCircular": False,
        }

    return _make


@pytest.fixture
def make_edge() -> Callable[..., dict]:
    def _make(source: str, target: str, *, is_circular: bool = False) -> dict:
        normalized_source = normalize_file_id(source)
        normalized_target = normalize_file_id(target)
        return {
            "id": f"{normalized_source}->{normalized_target}",
            "source": normalized_source,
            "target": normalized_target,
            "isCircular": is_circular,
        }

    return _make


@pytest.fixture
def make_dependency() -> Callable[..., dict]:
    def _make(dependency_id: str, *, label: str | None = None, type: str | None = None) -> dict:
        normalized = normalize_file_id(dependency_id)
        dependency_type = type or ("package" if normalized.startswith("pkg:") else "file")
        dependency_label = label
        if dependency_label is None:
            dependency_label = (
                normalized.removeprefix("pkg:")
                if dependency_type == "package"
                else normalized
            )
        return {
            "id": normalized,
            "label": dependency_label,
            "type": dependency_type,
        }

    return _make


@pytest.fixture
def make_parsed_file() -> Callable[..., dict]:
    def _make(
        file_id: str,
        *,
        language: str = "python",
        dependencies: list[dict] | None = None,
    ) -> dict:
        normalized = normalize_file_id(file_id)
        return {
            "id": normalized,
            "label": normalized,
            "type": "file",
            "language": language,
            "dependencies": dependencies or [],
        }

    return _make


@pytest.fixture
def write_project_files(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    def _write(files: dict[str, str]) -> Path:
        for relative_path, content in files.items():
            target_path = tmp_path / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        return tmp_path

    return _write


class GitRepo:
    def __init__(self, root: Path):
        self.root = root

    def run(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", *list(args)],
            cwd=self.root,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )

    def commit_file(self, path: str, content: str, message: str) -> str:
        full_path = self.root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        self.run("add", path)
        self.run("commit", "-m", message)
        return self.run("rev-parse", "HEAD").strip()


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> GitRepo:
    repo = GitRepo(tmp_path)
    repo.run("init")
    repo.run("config", "user.name", "ArchMAP Test")
    repo.run("config", "user.email", "test@archmap.local")
    repo.run("config", "commit.gpgsign", "false")
    # Ensure a consistent branch name
    try:
        repo.run("checkout", "-b", "main")
    except subprocess.CalledProcessError:
        # Some git versions might not like checkout -b on empty repo
        pass
    return repo
