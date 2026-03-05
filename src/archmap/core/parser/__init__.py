from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath
from typing import TypedDict

from archmap.core.parser.js_parser import parse_js_imports
from archmap.core.parser.python_parser import PythonImportEntry, parse_python_imports
from archmap.core.parser.rust_parser import RustImportEntry, parse_rust_imports
from archmap.core.parser.ts_parser import parse_ts_imports
from archmap.utils.file_utils import (
    JS_TS_EXTENSIONS,
    discover_source_files,
    file_language_from_id,
    normalize_file_id,
    to_file_id,
)

JS_TS_RESOLUTION_EXTENSIONS = sorted(JS_TS_EXTENSIONS | {".json"})


class Dependency(TypedDict):
    id: str
    label: str
    type: str


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
    project_path: str | Path, virtual_files: dict[str, str] | None = None
) -> ParsedProject:
    project_root = Path(project_path).resolve()
    file_content_map = _load_source_map(project_root, virtual_files)
    file_ids = set(file_content_map.keys())

    parsed_files: list[ParsedFile] = []

    for file_id in sorted(file_content_map.keys()):
        language = file_language_from_id(file_id)
        if language is None:
            continue

        source_code = file_content_map[file_id]
        imports = _parse_imports(language, source_code)
        dependencies = _resolve_dependencies(file_id, language, imports, file_ids)

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
    project_root: Path, virtual_files: dict[str, str] | None
) -> dict[str, str]:
    if virtual_files is not None:
        source_map: dict[str, str] = {}
        for file_id, content in virtual_files.items():
            normalized = normalize_file_id(file_id)
            if file_language_from_id(normalized) is None:
                continue
            source_map[normalized] = content
        return source_map

    source_map = {}
    for file_path in discover_source_files(project_root):
        file_id = to_file_id(project_root, file_path)
        try:
            source_map[file_id] = file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        except OSError:
            continue
    return source_map


def _parse_imports(
    language: str, source_code: str
) -> list[str] | list[PythonImportEntry] | list[RustImportEntry]:
    if language == "javascript":
        return parse_js_imports(source_code)
    if language == "typescript":
        return parse_ts_imports(source_code)
    if language == "python":
        return parse_python_imports(source_code)
    if language == "rust":
        return parse_rust_imports(source_code)
    return []


def _resolve_dependencies(
    file_id: str,
    language: str,
    imports: list[str] | list[PythonImportEntry] | list[RustImportEntry],
    file_ids: set[str],
) -> list[Dependency]:
    resolved: list[Dependency] = []

    if language in {"javascript", "typescript"}:
        for specifier in imports:
            if not isinstance(specifier, str):
                continue
            dependency = _resolve_js_ts_dependency(specifier, file_id, file_ids)
            if dependency:
                resolved.append(dependency)

    elif language == "python":
        for import_entry in imports:
            if not isinstance(import_entry, dict):
                continue
            resolved.extend(_resolve_python_dependency(import_entry, file_id, file_ids))

    elif language == "rust":
        for import_entry in imports:
            if not isinstance(import_entry, dict):
                continue
            resolved.extend(_resolve_rust_dependency(import_entry, file_id, file_ids))

    return _dedupe_dependencies(resolved)


def _resolve_js_ts_dependency(
    specifier: str, file_id: str, file_ids: set[str]
) -> Dependency | None:
    if specifier.startswith(".") or specifier.startswith("/"):
        if specifier.startswith("/"):
            base_candidate = normalize_file_id(specifier.lstrip("/"))
        else:
            base_dir = normalize_file_id(posixpath.dirname(file_id))
            base_candidate = _safe_norm_join(base_dir, specifier)

        if not base_candidate:
            return None

        match = _find_matching_file(base_candidate, JS_TS_RESOLUTION_EXTENSIONS, file_ids)
        if match:
            return _make_file_dependency(match)
        return None

    package_name = _extract_package_name(specifier)
    if package_name:
        return _make_package_dependency(package_name)
    return None


def _resolve_python_dependency(
    import_entry: PythonImportEntry, file_id: str, file_ids: set[str]
) -> list[Dependency]:
    import_type = import_entry.get("type")
    module_name = import_entry.get("module", "")

    if import_type == "import":
        internal_path = _find_python_absolute_module(module_name, file_ids)
        if internal_path:
            return [_make_file_dependency(internal_path)]

        package_name = _extract_package_name(module_name)
        return [_make_package_dependency(package_name)] if package_name else []

    if import_type == "from":
        if module_name.startswith("."):
            return _resolve_relative_python_from(
                module_name,
                import_entry.get("names", []),
                file_id,
                file_ids,
            )

        internal_path = _find_python_absolute_module(module_name, file_ids)
        if internal_path:
            return [_make_file_dependency(internal_path)]

        package_name = _extract_package_name(module_name)
        return [_make_package_dependency(package_name)] if package_name else []

    return []


def _resolve_relative_python_from(
    module_path: str, imported_names: list[str], file_id: str, file_ids: set[str]
) -> list[Dependency]:
    dot_count = len(module_path) - len(module_path.lstrip("."))
    remainder = module_path[dot_count:]
    base_dir = normalize_file_id(posixpath.dirname(file_id))

    for _ in range(max(0, dot_count - 1)):
        base_dir = normalize_file_id(posixpath.dirname(base_dir))

    resolved: list[Dependency] = []

    if remainder:
        candidate = _safe_norm_join(base_dir, remainder.replace(".", "/"))
        internal = _find_python_module(candidate, file_ids)
        if internal:
            resolved.append(_make_file_dependency(internal))
    else:
        for imported_name in imported_names:
            if imported_name == "*":
                continue
            candidate = _safe_norm_join(base_dir, imported_name.replace(".", "/"))
            internal = _find_python_module(candidate, file_ids)
            if internal:
                resolved.append(_make_file_dependency(internal))

    return _dedupe_dependencies(resolved)


def _resolve_rust_dependency(
    import_entry: RustImportEntry, file_id: str, file_ids: set[str]
) -> list[Dependency]:
    entry_type = import_entry.get("type")

    if entry_type == "mod":
        module_name = import_entry.get("module", "").strip()
        if not module_name:
            return []
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        candidate = _safe_norm_join(base_dir, module_name)
        resolved = _find_rust_module(candidate, file_ids)
        return [_make_file_dependency(resolved)] if resolved else []

    if entry_type == "extern":
        crate_name = import_entry.get("crate", "").strip()
        return [_make_package_dependency(crate_name)] if crate_name else []

    if entry_type != "use":
        return []

    use_path = import_entry.get("path", "")
    source_root = _infer_rust_source_root(file_id)

    if use_path.startswith("crate::"):
        parts = [part for part in use_path.removeprefix("crate::").split("::") if part]
        resolved = _resolve_rust_path_by_prefix(source_root, parts, file_ids)
        return [_make_file_dependency(resolved)] if resolved else []

    if use_path.startswith("self::"):
        parts = [part for part in use_path.removeprefix("self::").split("::") if part]
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        resolved = _resolve_rust_path_by_prefix(base_dir, parts, file_ids)
        return [_make_file_dependency(resolved)] if resolved else []

    if use_path.startswith("super::"):
        parts = [part for part in use_path.split("::") if part]
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        while parts and parts[0] == "super":
            parts.pop(0)
            base_dir = normalize_file_id(posixpath.dirname(base_dir))

        resolved = _resolve_rust_path_by_prefix(base_dir, parts, file_ids)
        return [_make_file_dependency(resolved)] if resolved else []

    parts = [part for part in use_path.split("::") if part]
    resolved = _resolve_rust_path_by_prefix(source_root, parts, file_ids)
    if resolved:
        return [_make_file_dependency(resolved)]

    package_name = parts[0] if parts else ""
    return [_make_package_dependency(package_name)] if package_name else []


def _resolve_rust_path_by_prefix(
    base_dir: str, module_parts: list[str], file_ids: set[str]
) -> str | None:
    if not module_parts:
        return None

    for length in range(len(module_parts), 0, -1):
        candidate = _safe_norm_join(base_dir, *module_parts[:length])
        resolved = _find_rust_module(candidate, file_ids)
        if resolved:
            return resolved
    return None


def _infer_rust_source_root(file_id: str) -> str:
    parts = list(PurePosixPath(file_id).parts)
    if "src" in parts:
        index = parts.index("src")
        return normalize_file_id("/".join(parts[: index + 1]))
    return "."


def _find_python_absolute_module(module_name: str, file_ids: set[str]) -> str | None:
    if not module_name:
        return None
    base = normalize_file_id(module_name.replace(".", "/"))
    return _find_python_module(base, file_ids)


def _find_python_module(base_candidate: str, file_ids: set[str]) -> str | None:
    direct = normalize_file_id(f"{base_candidate}.py")
    if direct in file_ids:
        return direct

    init_module = normalize_file_id(f"{base_candidate}/__init__.py")
    if init_module in file_ids:
        return init_module

    return None


def _find_rust_module(base_candidate: str, file_ids: set[str]) -> str | None:
    direct = normalize_file_id(f"{base_candidate}.rs")
    if direct in file_ids:
        return direct

    nested = normalize_file_id(f"{base_candidate}/mod.rs")
    if nested in file_ids:
        return nested

    return None


def _find_matching_file(
    base_candidate: str, extensions: list[str], file_ids: set[str]
) -> str | None:
    normalized_base = normalize_file_id(base_candidate)
    if normalized_base in file_ids:
        return normalized_base

    if Path(normalized_base).suffix:
        return normalized_base if normalized_base in file_ids else None

    for extension in extensions:
        with_extension = normalize_file_id(f"{normalized_base}{extension}")
        if with_extension in file_ids:
            return with_extension

    for extension in extensions:
        index_candidate = normalize_file_id(f"{normalized_base}/index{extension}")
        if index_candidate in file_ids:
            return index_candidate

    return None


def _extract_package_name(specifier: str) -> str | None:
    if not specifier:
        return None

    if specifier.startswith("@"):
        parts = specifier.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return specifier

    return specifier.split("/", maxsplit=1)[0]


def _dedupe_dependencies(dependencies: list[Dependency]) -> list[Dependency]:
    seen: set[str] = set()
    deduped: list[Dependency] = []
    for dependency in dependencies:
        dependency_id = dependency.get("id")
        if not dependency_id or dependency_id in seen:
            continue
        seen.add(dependency_id)
        deduped.append(dependency)
    return deduped


def _make_file_dependency(file_id: str) -> Dependency:
    normalized = normalize_file_id(file_id)
    return {"id": normalized, "label": normalized, "type": "file"}


def _make_package_dependency(package_name: str) -> Dependency:
    name = package_name.strip()
    return {"id": f"pkg:{name}", "label": name, "type": "package"}


def _safe_norm_join(*parts: str) -> str:
    joined = "/".join(part for part in parts if part not in {"", "."})
    normalized = normalize_file_id(posixpath.normpath(joined or "."))

    if normalized.startswith("../") or normalized == "..":
        return ""
    return normalized
