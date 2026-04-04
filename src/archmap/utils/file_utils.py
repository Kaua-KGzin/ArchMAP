from __future__ import annotations

import os
from collections.abc import Iterable
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
) -> list[Path]:
    """
    Localiza arquivos de código fonte suportados no diretório do projeto.
    Utiliza os.scandir() por performance para evitar syscalls stat() redundantes.
    """
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

    ignored = _ignored_dir_names(extra_ignored_dirs)
    files: list[Path] = []

    def _scandir_recursive(current_path: str):
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.casefold() in ignored:
                                continue
                            _scandir_recursive(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext not in SUPPORTED_EXTENSIONS:
                                continue

                            if max_file_size_bytes > 0:
                                # entry.stat() em sistemas modernos (como Linux/Win)
                                # já contém o tamanho vindo do readdir(), sem nova syscall.
                                if entry.stat().st_size > max_file_size_bytes:
                                    continue

                            files.append(Path(entry.path))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

    _scandir_recursive(str(project_root))
    return sorted(files)


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
