from __future__ import annotations

from archmap.core.parser.bootstrap import ensure_default_registry
from archmap.core.parser.project_parser import (
    ParsedFile as ParsedFile,
)
from archmap.core.parser.project_parser import (
    ParsedProject as ParsedProject,
)
from archmap.core.parser.project_parser import (
    _load_source_map as _load_source_map,
)
from archmap.core.parser.project_parser import (
    _resolve_dependencies as _resolve_dependencies,
)
from archmap.core.parser.project_parser import (
    parse_project as parse_project,
)
from archmap.core.parser.registry import Dependency as Dependency
from archmap.core.parser.registry import registry as registry
from archmap.core.parser.resolvers import (
    _dedupe_dependencies as _dedupe_dependencies,
)
from archmap.core.parser.resolvers import (
    _extract_package_name as _extract_package_name,
)
from archmap.core.parser.resolvers import (
    _find_matching_file as _find_matching_file,
)
from archmap.core.parser.resolvers import (
    _find_python_absolute_module as _find_python_absolute_module,
)
from archmap.core.parser.resolvers import (
    _find_python_module as _find_python_module,
)
from archmap.core.parser.resolvers import (
    _find_rust_module as _find_rust_module,
)
from archmap.core.parser.resolvers import (
    _infer_python_package_root as _infer_python_package_root,
)
from archmap.core.parser.resolvers import (
    _infer_python_search_roots as _infer_python_search_roots,
)
from archmap.core.parser.resolvers import (
    _infer_python_source_root as _infer_python_source_root,
)
from archmap.core.parser.resolvers import (
    _infer_rust_source_root as _infer_rust_source_root,
)
from archmap.core.parser.resolvers import (
    _make_file_dependency as _make_file_dependency,
)
from archmap.core.parser.resolvers import (
    _make_package_dependency as _make_package_dependency,
)
from archmap.core.parser.resolvers import (
    _resolve_js_ts_dependency as _resolve_js_ts_dependency,
)
from archmap.core.parser.resolvers import (
    _resolve_python_dependency as _resolve_python_dependency,
)
from archmap.core.parser.resolvers import (
    _resolve_relative_python_from as _resolve_relative_python_from,
)
from archmap.core.parser.resolvers import (
    _resolve_rust_dependency as _resolve_rust_dependency,
)
from archmap.core.parser.resolvers import (
    _resolve_rust_path_by_prefix as _resolve_rust_path_by_prefix,
)
from archmap.core.parser.resolvers import (
    _safe_norm_join as _safe_norm_join,
)

ensure_default_registry()

__all__ = [
    "Dependency",
    "ParsedFile",
    "ParsedProject",
    "_dedupe_dependencies",
    "_extract_package_name",
    "_find_matching_file",
    "_find_python_absolute_module",
    "_find_python_module",
    "_find_rust_module",
    "_infer_python_package_root",
    "_infer_python_search_roots",
    "_infer_python_source_root",
    "_infer_rust_source_root",
    "_load_source_map",
    "_make_file_dependency",
    "_make_package_dependency",
    "_resolve_dependencies",
    "_resolve_js_ts_dependency",
    "_resolve_python_dependency",
    "_resolve_relative_python_from",
    "_resolve_rust_dependency",
    "_resolve_rust_path_by_prefix",
    "_safe_norm_join",
    "parse_project",
    "registry",
]
