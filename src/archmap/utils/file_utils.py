from __future__ import annotations

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
}

JS_TS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
DEFAULT_IGNORE_DIRS = {
    ".git",
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
}


def normalize_file_id(file_id: str) -> str:
    normalized = str(PurePosixPath(file_id.replace("\\", "/")))
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def file_language_from_id(file_id: str) -> str | None:
    return SUPPORTED_EXTENSIONS.get(Path(file_id).suffix.lower())


def should_ignore_parts(parts: Iterable[str]) -> bool:
    return any(part in DEFAULT_IGNORE_DIRS for part in parts)


def discover_source_files(project_root: Path) -> list[Path]:
    files: list[Path] = []

    for file_path in project_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if should_ignore_parts(file_path.relative_to(project_root).parts):
            continue
        files.append(file_path)

    return sorted(files)


def to_file_id(project_root: Path, file_path: Path) -> str:
    return normalize_file_id(file_path.relative_to(project_root).as_posix())


def first_segment(file_id: str) -> str:
    parts = normalize_file_id(file_id).split("/")
    return parts[0] if len(parts) > 1 else "."


def ensure_parent_dir(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


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
