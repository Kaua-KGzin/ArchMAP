"""Tree-sitter engine for multi-language import extraction.

Falls back gracefully when tree-sitter is not installed.
Install the optional extra to enable: pip install archmap[tree-sitter]
"""
from __future__ import annotations

import re as _re

HAS_TREE_SITTER = False

try:
    import tree_sitter_c as _tsc_lang
    import tree_sitter_c_sharp as _tscs
    import tree_sitter_cpp as _tscpp
    import tree_sitter_go as _tsgo
    import tree_sitter_java as _tsjava_lang
    import tree_sitter_javascript as _tsjava
    import tree_sitter_php as _tsphp
    import tree_sitter_rust as _tsrust
    import tree_sitter_typescript as _tsts
    from tree_sitter import Language, Parser, Query, QueryCursor

    _JS_LANGUAGE = Language(_tsjava.language())
    _TS_LANGUAGE = Language(_tsts.language_typescript())
    _TSX_LANGUAGE = Language(_tsts.language_tsx())
    _JAVA_LANGUAGE = Language(_tsjava_lang.language())
    _GO_LANGUAGE = Language(_tsgo.language())
    _RUST_LANGUAGE = Language(_tsrust.language())
    _PHP_LANGUAGE = Language(_tsphp.language_php())
    _CS_LANGUAGE = Language(_tscs.language())
    _C_LANGUAGE = Language(_tsc_lang.language())
    _CPP_LANGUAGE = Language(_tscpp.language())
    HAS_TREE_SITTER = True
except (ImportError, AttributeError):
    pass


# ---------------------------------------------------------------------------
# Query strings
# ---------------------------------------------------------------------------

# JS/TS: ESM import/export-from, require(), dynamic import()
# @_fn is an auxiliary capture used only by the #eq? predicate.
_JS_QUERY_SRC = """
(import_statement source: (string (string_fragment) @specifier))
(export_statement source: (string (string_fragment) @specifier))
(call_expression
  function: (identifier) @_fn (#eq? @_fn "require")
  arguments: (arguments (string (string_fragment) @specifier)))
(call_expression
  function: (import)
  arguments: (arguments (string (string_fragment) @specifier)))
"""

_JAVA_QUERY_SRC = "(import_declaration) @decl"

_GO_QUERY_SRC = """
(import_spec path: (interpreted_string_literal
  (interpreted_string_literal_content) @path))
"""

_RUST_USE_QUERY_SRC = "(use_declaration argument: (_) @arg)"
_RUST_MOD_QUERY_SRC = "(mod_item name: (identifier) @name)"
_RUST_EXTERN_QUERY_SRC = "(extern_crate_declaration name: (identifier) @name)"

_PHP_USE_QUERY_SRC = "(namespace_use_declaration) @decl"
# Capture the expression node; string content is extracted in Python to handle
# both single-quoted (string) and double-quoted (encapsed_string) PHP strings
# as well as the parenthesized call form: require('x') vs require 'x'.
_PHP_REQUIRE_QUERY_SRC = "[(require_expression) @req (require_once_expression) @req]"
_PHP_INCLUDE_QUERY_SRC = "[(include_expression) @inc (include_once_expression) @inc]"

_CS_QUERY_SRC = "(using_directive) @decl"

_INCLUDE_QUERY_SRC = "(preproc_include) @inc"

if HAS_TREE_SITTER:
    _JS_QUERY = Query(_JS_LANGUAGE, _JS_QUERY_SRC)
    _TS_QUERY = Query(_TS_LANGUAGE, _JS_QUERY_SRC)
    _TSX_QUERY = Query(_TSX_LANGUAGE, _JS_QUERY_SRC)
    _JAVA_QUERY = Query(_JAVA_LANGUAGE, _JAVA_QUERY_SRC)
    _GO_QUERY = Query(_GO_LANGUAGE, _GO_QUERY_SRC)
    _RUST_USE_QUERY = Query(_RUST_LANGUAGE, _RUST_USE_QUERY_SRC)
    _RUST_MOD_QUERY = Query(_RUST_LANGUAGE, _RUST_MOD_QUERY_SRC)
    _RUST_EXTERN_QUERY = Query(_RUST_LANGUAGE, _RUST_EXTERN_QUERY_SRC)
    _PHP_USE_QUERY = Query(_PHP_LANGUAGE, _PHP_USE_QUERY_SRC)
    _PHP_REQUIRE_QUERY = Query(_PHP_LANGUAGE, _PHP_REQUIRE_QUERY_SRC)
    _PHP_INCLUDE_QUERY = Query(_PHP_LANGUAGE, _PHP_INCLUDE_QUERY_SRC)
    _CS_QUERY = Query(_CS_LANGUAGE, _CS_QUERY_SRC)
    _C_INCLUDE_QUERY = Query(_C_LANGUAGE, _INCLUDE_QUERY_SRC)
    _CPP_INCLUDE_QUERY = Query(_CPP_LANGUAGE, _INCLUDE_QUERY_SRC)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _captures(query: Query, tree: object) -> dict[str, list]:
    """Run a query and return captures sorted by document position."""
    cursor = QueryCursor(query)
    raw = cursor.captures(tree.root_node)  # type: ignore[attr-defined]
    if isinstance(raw, dict):
        # tree-sitter 0.24+ returns dict[str, list[Node]].
        # The internal ordering is not guaranteed to be document order, so sort.
        return {
            k: sorted(v, key=lambda n: (n.start_point.row, n.start_point.column))
            for k, v in raw.items()
        }
    # Older versions return list[tuple[Node, str]] — already in document order.
    result: dict[str, list] = {}
    for node, name in raw:
        result.setdefault(name, []).append(node)
    return result


def _parse(language: Language, source_code: str) -> object:
    return Parser(language).parse(source_code.encode("utf-8"))


def _text(node: object) -> str:
    raw = getattr(node, "text", None)
    return raw.decode("utf-8") if raw else ""


def _find_string_content(node: object) -> str | None:
    """Recursively find the first string_content node in a subtree."""
    if getattr(node, "type", "") == "string_content":
        return _text(node)
    for child in getattr(node, "named_children", []):
        result = _find_string_content(child)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# JavaScript / TypeScript
# ---------------------------------------------------------------------------

def extract_js_imports(source_code: str) -> list[str]:
    """Parse JavaScript and return sorted, deduplicated import specifiers."""
    tree = _parse(_JS_LANGUAGE, source_code)
    return _collect_specifiers(_captures(_JS_QUERY, tree))


def extract_ts_imports(source_code: str, tsx: bool = False) -> list[str]:
    """Parse TypeScript and return sorted, deduplicated import specifiers."""
    lang = _TSX_LANGUAGE if tsx else _TS_LANGUAGE
    query = _TSX_QUERY if tsx else _TS_QUERY
    tree = _parse(lang, source_code)
    return _collect_specifiers(_captures(query, tree))


def _collect_specifiers(caps: dict) -> list[str]:
    specifiers: set[str] = set()
    for node in caps.get("specifier", []):
        val = _text(node)
        if val:
            specifiers.add(val)
    return sorted(specifiers)


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

def extract_java_imports(source_code: str) -> list[str]:
    """Parse Java and return sorted, deduplicated import strings."""
    tree = _parse(_JAVA_LANGUAGE, source_code)
    results: set[str] = set()
    for node in _captures(_JAVA_QUERY, tree).get("decl", []):
        # "import static org.junit.Assert.assertEquals;" → "org.junit.Assert.assertEquals"
        raw = _text(node).strip().removeprefix("import ").removeprefix("static ")
        val = raw.removesuffix(";").strip()
        if val:
            results.add(val)
    return sorted(results)


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

def extract_go_imports(source_code: str) -> list[str]:
    """Parse Go and return sorted, deduplicated import paths."""
    tree = _parse(_GO_LANGUAGE, source_code)
    results: set[str] = set()
    for node in _captures(_GO_QUERY, tree).get("path", []):
        val = _text(node)
        if val:
            results.add(val)
    return sorted(results)


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

def extract_rust_imports(source_code: str) -> list[dict]:
    """Parse Rust and return import entries compatible with RustImportEntry."""
    tree = _parse(_RUST_LANGUAGE, source_code)
    results: list[dict] = []

    for node in _captures(_RUST_USE_QUERY, tree).get("arg", []):
        normalized = _normalize_rust_use(_text(node))
        if normalized:
            results.append({"type": "use", "path": normalized, "module": "", "crate": ""})

    for node in _captures(_RUST_MOD_QUERY, tree).get("name", []):
        val = _text(node)
        if val:
            results.append({"type": "mod", "path": "", "module": val, "crate": ""})

    for node in _captures(_RUST_EXTERN_QUERY, tree).get("name", []):
        val = _text(node)
        if val:
            results.append({"type": "extern", "path": "", "module": "", "crate": val})

    return results


def _normalize_rust_use(raw_path: str) -> str:
    compact = " ".join(raw_path.split()).removeprefix("pub ").strip()
    without_alias = compact.split(" as ", maxsplit=1)[0].strip()
    without_group = _re.sub(r"\{.*\}", "", without_alias).strip()
    without_wildcard = without_group.removesuffix("::*").strip()
    return without_wildcard.removesuffix("::").strip()


# ---------------------------------------------------------------------------
# PHP
# ---------------------------------------------------------------------------

def extract_php_imports(source_code: str) -> list[dict]:
    """Parse PHP and return import entries compatible with PHPImportEntry."""
    tree = _parse(_PHP_LANGUAGE, source_code)
    results: list[dict] = []

    for node in _captures(_PHP_USE_QUERY, tree).get("decl", []):
        val = _text(node).strip().removeprefix("use ").removesuffix(";").strip()
        if val:
            results.append({"type": "use", "value": val})

    for node in _captures(_PHP_REQUIRE_QUERY, tree).get("req", []):
        val = _find_string_content(node)
        if val:
            results.append({"type": "require", "value": val})

    for node in _captures(_PHP_INCLUDE_QUERY, tree).get("inc", []):
        val = _find_string_content(node)
        if val:
            results.append({"type": "include", "value": val})

    return results


# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------

def extract_csharp_imports(source_code: str) -> list[str]:
    """Parse C# and return sorted, deduplicated using namespace strings."""
    tree = _parse(_CS_LANGUAGE, source_code)
    results: set[str] = set()
    for node in _captures(_CS_QUERY, tree).get("decl", []):
        val = _text(node).strip().removeprefix("using ").removesuffix(";").strip()
        if val:
            results.add(val)
    return sorted(results)


# ---------------------------------------------------------------------------
# C / C++
# ---------------------------------------------------------------------------

def extract_c_includes(source_code: str) -> list[dict]:
    """Parse C and return include entries compatible with CppImportEntry."""
    return _extract_includes(_C_LANGUAGE, _C_INCLUDE_QUERY, source_code)


def extract_cpp_includes(source_code: str) -> list[dict]:
    """Parse C++ and return include entries compatible with CppImportEntry."""
    return _extract_includes(_CPP_LANGUAGE, _CPP_INCLUDE_QUERY, source_code)


def _extract_includes(language: Language, query: Query, source_code: str) -> list[dict]:
    tree = _parse(language, source_code)
    results: list[dict] = []
    for inc_node in _captures(query, tree).get("inc", []):
        for child in inc_node.children:  # type: ignore[attr-defined]
            if getattr(child, "type", "") == "system_lib_string":
                raw = _text(child)
                results.append({"type": "system", "value": raw[1:-1]})  # strip < >
                break
            if getattr(child, "type", "") == "string_literal":
                inner = next(
                    (
                        _text(c)
                        for c in getattr(child, "named_children", [])
                        if getattr(c, "type", "") == "string_content"
                    ),
                    _text(child).strip('"'),
                )
                results.append({"type": "local", "value": inner})
                break
    return results
