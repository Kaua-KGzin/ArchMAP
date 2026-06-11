from __future__ import annotations

import posixpath
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from archmap.core.parser.registry import Dependency
from archmap.utils.file_utils import JS_TS_EXTENSIONS, normalize_file_id

JS_TS_RESOLUTION_EXTENSIONS = sorted(JS_TS_EXTENSIONS | {".json"})


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
    import_entry: Mapping[str, Any], file_id: str, file_ids: set[str]
) -> list[Dependency]:
    import_type = import_entry.get("type")
    module_name = str(import_entry.get("module", ""))

    if import_type == "import":
        internal_path = _find_python_absolute_module(module_name, file_ids, file_id)
        if internal_path:
            return [_make_file_dependency(internal_path)]

        package_name = _extract_package_name(module_name)
        return [_make_package_dependency(package_name)] if package_name else []

    if import_type == "from":
        if module_name.startswith("."):
            return _resolve_relative_python_from(
                module_name,
                [str(name) for name in import_entry.get("names", [])],
                file_id,
                file_ids,
            )

        internal_path = _find_python_absolute_module(module_name, file_ids, file_id)

        # Check each imported name as a potential submodule of module_name.
        # e.g. `from pkg import utils` may resolve to `pkg/utils.py`.
        submodule_deps: list[Dependency] = []
        for name in import_entry.get("names", []):
            if name == "*":
                continue
            sub_path = _find_python_absolute_module(f"{module_name}.{name}", file_ids, file_id)
            if sub_path:
                submodule_deps.append(_make_file_dependency(sub_path))

        if submodule_deps:
            return submodule_deps

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
    import_entry: Mapping[str, Any], file_id: str, file_ids: set[str]
) -> list[Dependency]:
    entry_type = import_entry.get("type")

    if entry_type == "mod":
        module_name = str(import_entry.get("module", "")).strip()
        if not module_name:
            return []
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        candidate = _safe_norm_join(base_dir, module_name)
        resolved = _find_rust_module(candidate, file_ids)
        return [_make_file_dependency(resolved)] if resolved else []

    if entry_type == "extern":
        crate_name = str(import_entry.get("crate", "")).strip()
        return [_make_package_dependency(crate_name)] if crate_name else []

    if entry_type != "use":
        return []

    use_path = str(import_entry.get("path", ""))
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


def _infer_python_search_roots(file_id: str, file_ids: set[str]) -> list[str]:
    roots: list[str] = []

    for root in (
        _infer_python_source_root(file_id),
        _infer_python_package_root(file_id, file_ids),
    ):
        if root in {"", "."} or root in roots:
            continue
        roots.append(root)

    return roots


def _infer_python_source_root(file_id: str) -> str:
    parts = list(PurePosixPath(normalize_file_id(file_id)).parts)
    if "src" in parts:
        index = parts.index("src")
        return normalize_file_id("/".join(parts[: index + 1]))
    return "."


def _infer_python_package_root(file_id: str, file_ids: set[str]) -> str:
    current_dir = normalize_file_id(posixpath.dirname(file_id))
    top_package_dir = ""

    while current_dir not in {"", "."}:
        init_module = normalize_file_id(f"{current_dir}/__init__.py")
        if init_module not in file_ids:
            break

        top_package_dir = current_dir
        parent_dir = normalize_file_id(posixpath.dirname(current_dir))
        if parent_dir == current_dir:
            break
        current_dir = parent_dir

    if not top_package_dir:
        return "."

    return normalize_file_id(posixpath.dirname(top_package_dir))


def _find_python_absolute_module(
    module_name: str, file_ids: set[str], importer_file_id: str | None = None
) -> str | None:
    if not module_name:
        return None

    base = normalize_file_id(module_name.replace(".", "/"))
    candidates = [base]

    if importer_file_id:
        for root in _infer_python_search_roots(importer_file_id, file_ids):
            candidate = _safe_norm_join(root, base)
            if candidate and candidate not in candidates:
                candidates.append(candidate)

    for candidate in candidates:
        resolved = _find_python_module(candidate, file_ids)
        if resolved:
            return resolved

    return None


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


def _resolve_go_dependency(
    import_entries: list[Any],
    file_id: str,
    file_ids: set[str],
    module_name: str | None,
    replacements: dict[str, str] | None = None,
) -> list[Dependency]:
    resolved: list[Dependency] = []
    replacements = replacements or {}

    def _collect_dir(package_dir: str) -> bool:
        normalized_dir = normalize_file_id(package_dir).strip("/")
        found = False
        for fid in file_ids:
            if normalize_file_id(posixpath.dirname(fid)) == normalized_dir and fid.endswith(
                ".go"
            ):
                resolved.append(_make_file_dependency(fid))
                found = True
        return found

    for specifier in import_entries:
        if not isinstance(specifier, str) or not specifier:
            continue

        if module_name and (specifier == module_name or specifier.startswith(module_name + "/")):
            package_dir = "" if specifier == module_name else specifier[len(module_name) + 1 :]
            if _collect_dir(package_dir):
                continue

        # go.mod replace directive pointing at a local module path
        replaced_dir = _match_go_replacement(specifier, replacements)
        if replaced_dir is not None and _collect_dir(replaced_dir):
            continue

        resolved.append(_make_package_dependency(specifier))

    return _dedupe_dependencies(resolved)


def _match_go_replacement(specifier: str, replacements: dict[str, str]) -> str | None:
    """Map an import path to a local directory via go.mod replace, if any."""
    for old, target in replacements.items():
        if specifier == old or specifier.startswith(old + "/"):
            sub = "" if specifier == old else specifier[len(old) + 1 :]
            local = target.removeprefix("./")
            return _safe_norm_join(local, sub) if sub else _safe_norm_join(local)
    return None


def _resolve_php_dependency(
    import_entry: Mapping[str, Any],
    file_id: str,
    file_ids: set[str],
    psr4: dict[str, list[str]] | None = None,
) -> list[Dependency]:
    entry_type = import_entry.get("type")
    value = str(import_entry.get("value", "")).strip()

    if not value:
        return []

    if entry_type in ("require", "include"):
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        candidate = _safe_norm_join(base_dir, value)

        match = _find_php_module(candidate, file_ids)
        if match:
            return [_make_file_dependency(match)]

        return [_make_package_dependency(value)]

    if entry_type == "use":
        # composer PSR-4 autoload takes precedence over heuristic suffix matching.
        psr4_match = _resolve_php_psr4(value, psr4 or {}, file_ids)
        if psr4_match:
            return [_make_file_dependency(psr4_match)]

        path_candidate = normalize_file_id(value.replace("\\", "/"))

        parts = path_candidate.split("/")
        for i in range(len(parts)):
            partial_path = "/".join(parts[i:])
            normalized_candidate = partial_path.casefold() + ".php"

            for fid in file_ids:
                if (
                    fid.casefold() == normalized_candidate
                    or fid.casefold().endswith("/" + normalized_candidate)
                ):
                    return [_make_file_dependency(fid)]

        match = _find_php_module(path_candidate, file_ids)
        if match:
            return [_make_file_dependency(match)]

        return [_make_package_dependency(value)]

    return []


def _resolve_php_psr4(
    namespace: str, psr4: dict[str, list[str]], file_ids: set[str]
) -> str | None:
    """Resolve a PHP namespace via composer PSR-4 autoload prefixes.

    e.g. with {"App\\": "src/"}, ``App\\Models\\User`` -> ``src/Models/User.php``.
    Longest matching prefix wins, as PSR-4 mandates.
    """
    if not psr4:
        return None

    norm_ns = namespace.lstrip("\\")
    for prefix in sorted(psr4, key=len, reverse=True):
        clean_prefix = prefix.rstrip("\\")
        if clean_prefix and not (
            norm_ns == clean_prefix or norm_ns.startswith(clean_prefix + "\\")
        ):
            continue
        remainder = norm_ns[len(clean_prefix):].lstrip("\\") if clean_prefix else norm_ns
        sub_path = remainder.replace("\\", "/")
        for base_dir in psr4[prefix]:
            candidate = _safe_norm_join(normalize_file_id(base_dir.rstrip("/")), sub_path)
            match = _find_php_module(candidate, file_ids)
            if match:
                return match
    return None


def _find_php_module(base_candidate: str, file_ids: set[str]) -> str | None:
    direct = normalize_file_id(f"{base_candidate}.php")
    if direct in file_ids:
        return direct
    if normalize_file_id(base_candidate) in file_ids:
        return normalize_file_id(base_candidate)
    return None


def _resolve_java_dependency(
    specifier: str, file_id: str, file_ids: set[str]
) -> list[Dependency]:
    if not specifier:
        return []

    if specifier.startswith(("java.", "javax.", "sun.")):
        return [_make_package_dependency(specifier)]

    if specifier.endswith(".*"):
        package_prefix = specifier[:-2]
        package_dir = package_prefix.replace(".", "/")
        normalized_dir = normalize_file_id(package_dir).casefold()

        resolved: list[Dependency] = []
        for fid in file_ids:
            normalized_dirname = normalize_file_id(posixpath.dirname(fid)).casefold()
            if fid.endswith(".java") and normalized_dirname.endswith(normalized_dir):
                resolved.append(_make_file_dependency(fid))

        if resolved:
            return resolved
        return [_make_package_dependency(specifier)]

    segments = specifier.split(".")
    # Try the full path first, then progressively treat trailing segments as
    # inner classes: `com.example.Outer.Inner` may live in `com/example/Outer.java`.
    for cut in range(len(segments), 1, -1):
        path_candidate = normalize_file_id("/".join(segments[:cut])) + ".java"
        normalized_candidate = path_candidate.casefold()
        for fid in file_ids:
            if fid.casefold().endswith(normalized_candidate):
                return [_make_file_dependency(fid)]

    return [_make_package_dependency(specifier)]


def _resolve_cpp_dependency(
    import_entry: Mapping[str, Any], file_id: str, file_ids: set[str]
) -> list[Dependency]:
    entry_type = import_entry.get("type")
    value = str(import_entry.get("value", "")).strip()

    if not value:
        return []

    if entry_type == "system":
        return [_make_package_dependency(value)]

    if entry_type == "local":
        base_dir = normalize_file_id(posixpath.dirname(file_id))
        relative_candidate = _safe_norm_join(base_dir, value)

        if relative_candidate in file_ids:
            return [_make_file_dependency(relative_candidate)]

        absolute_candidate = normalize_file_id(value)
        if absolute_candidate in file_ids:
            return [_make_file_dependency(absolute_candidate)]

        # Fallback for projects that compile with -I include dirs: a header
        # included as "foo/bar.h" frequently lives at include/foo/bar.h or
        # src/foo/bar.h. Match by unique path suffix.
        suffix = "/" + absolute_candidate
        suffix_matches = [fid for fid in file_ids if fid.endswith(suffix)]
        if len(suffix_matches) == 1:
            return [_make_file_dependency(suffix_matches[0])]

        return [_make_package_dependency(value)]

    return []


def _resolve_csharp_dependency(
    specifier: str, file_id: str, file_ids: set[str]
) -> list[Dependency]:
    if not specifier:
        return []

    if specifier.startswith("static "):
        specifier = specifier[7:].strip()

    if specifier.startswith(("System.", "System;", "Microsoft.", "Microsoft;", "Newtonsoft.")):
        return [_make_package_dependency(specifier)]

    path_candidate = normalize_file_id(specifier.replace(".", "/"))

    parts = path_candidate.split("/")
    resolved: list[Dependency] = []

    for i in range(len(parts)):
        partial_path = "/".join(parts[i:])
        normalized_candidate = partial_path.casefold()

        for fid in file_ids:
            normalized_dirname = normalize_file_id(posixpath.dirname(fid)).casefold()
            if fid.endswith(".cs") and normalized_dirname.endswith(normalized_candidate):
                resolved.append(_make_file_dependency(fid))

        if not resolved:
            file_candidate = normalized_candidate + ".cs"
            for fid in file_ids:
                if (
                    fid.casefold() == file_candidate
                    or fid.casefold().endswith("/" + file_candidate)
                ):
                    resolved.append(_make_file_dependency(fid))

        if resolved:
            return resolved

    return [_make_package_dependency(specifier)]
