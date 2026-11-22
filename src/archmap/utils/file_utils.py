from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath

SUPPORTED_EXTENSIONS = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".py": "python",
    ".rs": "rust",
    ".go": "go",
    ".php": "php",
    ".java": "java",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
}

JS_TS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
DEFAULT_IGNORE_DIRS = {
    ".git",
    ".codeatlas",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "site",
    "tests",
    "examples",
}


# Third-party code copied into a repository. It is kept in the graph (it is
# real code the project links) but must not dominate risk rankings or be
# reported as the project's own vulnerabilities.
VENDOR_DIR_NAMES = frozenset({
    "vendor", "vendors", "vendored", "third_party", "third-party", "thirdparty",
    "3rdparty", "extern", "ext", "deps", "external_libs", "contrib",
})
VENDOR_LIBRARY_NAMES = frozenset({
    "imgui", "stb", "glad", "glfw", "glm", "minhook", "detours", "nlohmann", "rapidjson",
    "spdlog", "freetype", "lua", "luajit", "sqlite3", "zlib", "curl", "openssl", "boost",
    "eigen", "catch2", "gtest", "googletest", "doctest", "json-c", "cjson", "miniaudio",
})


def is_vendored_path(file_id: str) -> bool:
    """True when ``file_id`` sits in a vendored/third-party directory."""
    parts = [p.casefold() for p in normalize_file_id(file_id).split("/")[:-1]]
    return any(p in VENDOR_DIR_NAMES or p in VENDOR_LIBRARY_NAMES for p in parts)


def normalize_file_id(file_id: str) -> str:
    normalized = str(PurePosixPath(file_id.replace("\\", "/")))
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def file_language_from_id(file_id: str) -> str | None:
    return SUPPORTED_EXTENSIONS.get(Path(file_id).suffix.lower())


def should_ignore_parts(
    parts: Iterable[str], extra_ignored_dirs: Iterable[str] | None = None
) -> bool:
    ignored_dirs = _ignored_dir_names(extra_ignored_dirs)
    return any(part.casefold() in ignored_dirs for part in parts)


def discover_source_files(
    project_root: Path,
    extra_ignored_dirs: Iterable[str] | None = None,
    max_file_size_bytes: int = 0,
    respect_gitignore: bool = False,
) -> list[Path]:
    if project_root.is_file():
        if project_root.suffix.lower() in SUPPORTED_EXTENSIONS:
            if max_file_size_bytes > 0:
                try:
                    if project_root.stat().st_size > max_file_size_bytes:
                        return []
                except OSError:
                    return []
            return [project_root]
        return []

    files: list[Path] = []

    for file_path in walk_project_files(
        project_root, extra_ignored_dirs, respect_gitignore=respect_gitignore
    ):
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if max_file_size_bytes > 0:
            try:
                if file_path.stat().st_size > max_file_size_bytes:
                    continue
            except OSError:
                continue
        files.append(file_path)

    return sorted(files)


def walk_project_files(
    project_root: Path,
    extra_ignored_dirs: Iterable[str] | None = None,
    *,
    respect_gitignore: bool = False,
    unignore: Iterable[str] = (),
) -> Iterator[Path]:
    """Yield every file under ``project_root`` outside the ignored directories.

    Ignored directories are pruned before they are listed, so the cost scales
    with the project's own files rather than with ``node_modules``, ``.git``
    or a virtualenv. ``project_root`` itself is never checked, so analysing a
    directory that is named ``tests`` still works. Symlinked directories are
    not followed, as with ``Path.rglob``.

    With ``respect_gitignore`` the files and directories git reports as
    ignored are skipped too (see :func:`git_ignored_paths`); outside a git
    work tree, or without git, nothing extra is skipped. ``unignore`` lifts
    names from the built-in set (test discovery walks ``tests/``).
    """
    ignored = _ignored_dir_names(extra_ignored_dirs) - {d.casefold() for d in unignore}
    git_dirs: set[str] = set()
    git_files: set[str] = set()
    if respect_gitignore:
        git_dirs, git_files = git_ignored_paths(project_root) or (set(), set())
    for dirpath, dirnames, filenames in os.walk(project_root):
        base = Path(dirpath)
        rel = base.relative_to(project_root).as_posix() if git_dirs or git_files else ""
        prefix = "" if rel == "." else rel + "/"
        dirnames[:] = [
            d
            for d in dirnames
            if d.casefold() not in ignored and prefix + d not in git_dirs
        ]
        for name in filenames:
            if git_files and prefix + name in git_files:
                continue
            yield base / name


def git_ignored_paths(project_root: Path) -> tuple[set[str], set[str]] | None:
    """Untracked paths git ignores under ``project_root``, as (dirs, files).

    Asks git itself (``ls-files --others --ignored --exclude-standard
    --directory``), so nested ``.gitignore`` files, negations,
    ``.git/info/exclude`` and the global excludes file all apply exactly as
    they do for ``git status``. Tracked files are never reported, even when
    they match a pattern. Paths are relative to ``project_root``, and a fully
    ignored directory is reported once, so it can be pruned unwalked.
    Returns ``None`` outside a git work tree or when git is unavailable.
    """
    try:
        completed = subprocess.run(
            [
                "git", "-C", str(project_root), "ls-files", "-z",
                "--others", "--ignored", "--exclude-standard", "--directory",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    dirs: set[str] = set()
    files: set[str] = set()
    for entry in completed.stdout.decode("utf-8", "replace").split(chr(0)):
        if not entry or entry.startswith("../"):
            continue
        if entry.endswith("/"):
            dirs.add(entry.rstrip("/"))
        else:
            files.add(entry)
    return dirs, files


def to_file_id(project_root: Path, file_path: Path) -> str:
    if project_root.is_file() and project_root == file_path:
        return normalize_file_id(file_path.name)
    return normalize_file_id(file_path.relative_to(project_root).as_posix())


def first_segment(file_id: str) -> str:
    parts = normalize_file_id(file_id).split("/")
    return parts[0] if len(parts) > 1 else "."


def ensure_parent_dir(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def _ignored_dir_names(extra_ignored_dirs: Iterable[str] | None) -> set[str]:
    ignored = {part.casefold() for part in DEFAULT_IGNORE_DIRS}
    if extra_ignored_dirs is None:
        return ignored

    for value in extra_ignored_dirs:
        normalized = normalize_file_id(str(value)).strip("/")
        if not normalized:
            continue
        ignored.add(PurePosixPath(normalized).name.casefold())

    return ignored


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if q <= 0:
        return ordered[0]
    if q >= 1:
        return ordered[-1]

    index = int(round((len(ordered) - 1) * q))
    return ordered[index]
