from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from archmap.config import DEFAULT_MAX_FILE_SIZE_BYTES, ProjectConfig, load_project_config
from archmap.core.parser.bootstrap import ensure_default_registry
from archmap.core.parser.registry import Dependency, registry
from archmap.utils.file_utils import discover_source_files, normalize_file_id, to_file_id

ensure_default_registry()


class ParsedFile(TypedDict):
    id: str
    label: str
    type: str
    language: str
    dependencies: list[Dependency]


class ParsedProject(TypedDict):
    projectRoot: str
    parsedFiles: list[ParsedFile]


def parse_project(
    project_path: str | Path,
    virtual_files: dict[str, str] | None = None,
    config: ProjectConfig | None = None,
) -> ParsedProject:
    project_root = Path(project_path).resolve()
    active_config = config or load_project_config(project_root, virtual_files)
    file_content_map = _load_source_map(project_root, virtual_files, active_config)
    file_ids = set(file_content_map.keys())

    parsed_files: list[ParsedFile] = []

    for file_id in sorted(file_content_map.keys()):
        ext = Path(file_id).suffix.lower()
        language = registry.get_language_by_ext(ext)
        if not language:
            continue

        parser = registry.get_parser(language)
        if not parser:
            continue

        source_code = file_content_map[file_id]
        import_entries = parser.parse(source_code)
        dependencies = parser.resolve(import_entries, file_id, file_ids)

        parsed_files.append(
            {
                "id": file_id,
                "label": file_id,
                "type": "file",
                "language": language,
                "dependencies": dependencies,
            }
        )

    return {
        "projectRoot": str(project_root),
        "parsedFiles": parsed_files,
    }


def _load_source_map(
    project_root: Path,
    virtual_files: dict[str, str] | None,
    config: ProjectConfig | None = None,
) -> dict[str, str]:
    ensure_default_registry()
    active_config = config or load_project_config(project_root, virtual_files)
    extra_ignored_dirs = active_config["analysis"]["ignore_dirs"]
    max_file_size_bytes = active_config["analysis"].get(
        "max_file_size_bytes",
        DEFAULT_MAX_FILE_SIZE_BYTES,
    )
    ignored_dir_names = {entry.casefold() for entry in extra_ignored_dirs}

    if virtual_files is not None:
        source_map: dict[str, str] = {}
        for file_id, content in virtual_files.items():
            normalized = normalize_file_id(file_id)
            ext = Path(normalized).suffix.lower()
            if not registry.get_language_by_ext(ext):
                continue
            if extra_ignored_dirs and any(
                part.casefold() in ignored_dir_names
                for part in Path(normalized).parts
            ):
                continue
            if not _is_within_size_limit(len(content.encode("utf-8")), max_file_size_bytes):
                continue
            source_map[normalized] = content
        return source_map

    source_map = {}
    for file_path in discover_source_files(project_root, extra_ignored_dirs=extra_ignored_dirs):
        file_id = to_file_id(project_root, file_path)
        try:
            if not _is_within_size_limit(file_path.stat().st_size, max_file_size_bytes):
                continue
            source_map[file_id] = file_path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
    return source_map


def _resolve_dependencies(
    file_id: str,
    language: str,
    imports: list[Any],
    file_ids: set[str],
) -> list[Dependency]:
    ensure_default_registry()

    # Compatibility shim for older plugins and tests that still import this helper
    # from project_parser. New resolution logic should live on parser modules or
    # resolvers, and this helper stays stable until that deprecation path is closed.
    parser = registry.get_parser(language)
    if parser:
        return parser.resolve(imports, file_id, file_ids)
    return []


def _is_within_size_limit(file_size_bytes: int, max_file_size_bytes: int) -> bool:
    if max_file_size_bytes <= 0:
        return True
    return file_size_bytes <= max_file_size_bytes
