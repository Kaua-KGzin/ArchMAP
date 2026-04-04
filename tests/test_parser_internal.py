from pathlib import Path

from archmap.config import default_project_config
from archmap.core.parser import (
    _extract_package_name,
    _infer_rust_source_root,
    _load_source_map,
    _resolve_dependencies,
    _resolve_js_ts_dependency,
    _resolve_python_dependency,
    _resolve_rust_dependency,
    _safe_norm_join,
    parse_project,
)
from archmap.core.parser.bootstrap import ensure_default_registry, register_core_parsers
from archmap.core.parser.registry import LanguageRegistry, registry
from archmap.core.parser.ts_parser import TSParser


def test_extract_package_name():
    assert _extract_package_name("react") == "react"
    assert _extract_package_name("react/jsx-runtime") == "react"
    assert _extract_package_name("@mui/material") == "@mui/material"
    assert _extract_package_name("@mui/material/Button") == "@mui/material"
    assert _extract_package_name("") is None


def test_safe_norm_join():
    assert _safe_norm_join("src", "utils.js") == "src/utils.js"
    assert _safe_norm_join("src", ".", "utils.js") == "src/utils.js"
    assert _safe_norm_join("src/lib", "../utils.js") == "src/utils.js"
    assert _safe_norm_join("..", "src") == ""


def test_load_source_map_virtual():
    files = {"src/main.py": "print(1)", "README.md": "docs"}
    res = _load_source_map(Path("."), files)
    assert res == {"src/main.py": "print(1)"}  # md ignored


def test_load_source_map_virtual_honors_max_file_size() -> None:
    files = {
        "src/small.py": "print(1)\n",
        "src/large.py": "print('01234567890123456789')\n",
    }
    config = default_project_config()
    config["analysis"]["max_file_size_bytes"] = 12

    res = _load_source_map(Path("."), files, config=config)

    assert res == {"src/small.py": "print(1)\n"}


def test_load_source_map_real(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)")
    (tmp_path / "docs.md").write_text("docs")
    res = _load_source_map(tmp_path, None)
    assert res == {"src/main.py": "print(1)"}


def test_parse_project_virtual():
    files = {"main.py": "import os", "other.txt": "ignore"}
    res = parse_project("dummy", files)
    assert len(res["parsedFiles"]) == 1
    assert res["parsedFiles"][0]["id"] == "main.py"
    assert res["parsedFiles"][0]["language"] == "python"


def test_registry_exposes_typescript_parser_and_extensions():
    parser = registry.get_parser("typescript")
    assert parser is not None
    assert isinstance(parser, TSParser)
    assert registry.get_language_by_ext(".ts") == "typescript"
    assert registry.get_language_by_ext(".tsx") == "typescript"
    assert "typescript" in registry.get_all_languages()
    assert ".tsx" in registry.get_all_extensions()


def test_register_core_parsers_populates_fresh_registry():
    fresh_registry = LanguageRegistry()

    register_core_parsers(fresh_registry)

    assert fresh_registry.get_parser("python") is not None
    assert fresh_registry.get_parser("javascript") is not None
    assert isinstance(fresh_registry.get_parser("typescript"), TSParser)
    assert fresh_registry.get_parser("rust") is not None
    assert fresh_registry.get_parser("go") is not None
    assert fresh_registry.get_parser("php") is not None
    assert fresh_registry.get_parser("java") is not None
    assert fresh_registry.get_parser("c") is not None
    assert fresh_registry.get_parser("cpp") is not None


def test_ensure_default_registry_is_idempotent():
    before_languages = set(registry.get_all_languages())

    first = ensure_default_registry()
    second = ensure_default_registry()

    assert first is registry
    assert second is registry
    assert set(registry.get_all_languages()) == before_languages


def test_resolve_dependencies_unsupported():
    assert _resolve_dependencies("main.rs", "unknown", [], set()) == []


def test_resolve_js_ts_dependency():
    file_ids = {"src/utils.js", "src/index.js", "package.json"}

    # Internal resolve
    dep = _resolve_js_ts_dependency("./utils", "src/main.js", file_ids)
    assert dep == {"id": "src/utils.js", "label": "src/utils.js", "type": "file"}

    # Absolute internal
    dep = _resolve_js_ts_dependency("/src/utils", "src/other/test.js", file_ids)
    assert dep == {"id": "src/utils.js", "label": "src/utils.js", "type": "file"}

    # Missing internal
    assert _resolve_js_ts_dependency("./notFound", "src/main.js", file_ids) is None

    # External
    dep = _resolve_js_ts_dependency("react", "src/main.js", file_ids)
    assert dep == {"id": "pkg:react", "label": "react", "type": "package"}


def test_resolve_python_dependency():
    file_ids = {"app/utils.py", "app/services/__init__.py"}

    # Absolute import
    entry = {"type": "import", "module": "os", "names": []}
    res = _resolve_python_dependency(entry, "app/main.py", file_ids)
    assert res == [{"id": "pkg:os", "label": "os", "type": "package"}]

    entry = {"type": "import", "module": "app.utils", "names": []}
    res = _resolve_python_dependency(entry, "app/main.py", file_ids)
    assert res == [{"id": "app/utils.py", "label": "app/utils.py", "type": "file"}]

    # From import internal module
    entry = {"type": "from", "module": "app.services", "names": ["Auth"]}
    res = _resolve_python_dependency(entry, "app/main.py", file_ids)
    assert res == [
        {"id": "app/services/__init__.py", "label": "app/services/__init__.py", "type": "file"}
    ]

    # From import relative
    entry = {"type": "from", "module": ".utils", "names": ["helper"]}
    res = _resolve_python_dependency(entry, "app/main.py", file_ids)
    assert res == [{"id": "app/utils.py", "label": "app/utils.py", "type": "file"}]

    # External from
    entry = {"type": "from", "module": "fastapi", "names": ["FastAPI"]}
    res = _resolve_python_dependency(entry, "app/main.py", file_ids)
    assert res == [{"id": "pkg:fastapi", "label": "fastapi", "type": "package"}]




def test_resolve_rust_dependency():
    file_ids = {"src/main.rs", "src/core/mod.rs", "src/utils.rs"}

    # mod import
    entry = {"type": "mod", "module": "utils"}
    res = _resolve_rust_dependency(entry, "src/main.rs", file_ids)
    assert res == [{"id": "src/utils.rs", "label": "src/utils.rs", "type": "file"}]

    # extern crate
    entry = {"type": "extern", "crate": "serde"}
    res = _resolve_rust_dependency(entry, "src/main.rs", file_ids)
    assert res == [{"id": "pkg:serde", "label": "serde", "type": "package"}]

    # use crate::
    entry = {"type": "use", "path": "crate::core"}
    res = _resolve_rust_dependency(entry, "src/main.rs", file_ids)
    assert res == [{"id": "src/core/mod.rs", "label": "src/core/mod.rs", "type": "file"}]

    # use super::
    entry = {"type": "use", "path": "super::utils"}
    res = _resolve_rust_dependency(entry, "src/core/mod.rs", file_ids)
    assert res == [{"id": "src/utils.rs", "label": "src/utils.rs", "type": "file"}]

    # use third-party
    entry = {"type": "use", "path": "tokio::sync"}
    res = _resolve_rust_dependency(entry, "src/main.rs", file_ids)
    assert res == [{"id": "pkg:tokio", "label": "tokio", "type": "package"}]


def test_infer_rust_source_root():
    assert _infer_rust_source_root("src/main.rs") == "src"
    assert _infer_rust_source_root("src/core/mod.rs") == "src"
    assert _infer_rust_source_root("tests/test.rs") == "."
