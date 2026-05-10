"""Tree-sitter engine for JavaScript and TypeScript import extraction.

Falls back gracefully to regex-based parsing when tree-sitter is not installed.
Install the optional extra to enable: pip install archmap[tree-sitter]
"""
from __future__ import annotations

HAS_TREE_SITTER = False

try:
    import tree_sitter_javascript as _tsjava
    import tree_sitter_typescript as _tsts
    from tree_sitter import Language, Parser, Query, QueryCursor

    _JS_LANGUAGE = Language(_tsjava.language())
    _TS_LANGUAGE = Language(_tsts.language_typescript())
    _TSX_LANGUAGE = Language(_tsts.language_tsx())
    HAS_TREE_SITTER = True
except (ImportError, AttributeError):
    pass


# Captures ESM import/export-from, require(), and dynamic import().
# @_fn is an auxiliary capture used only to satisfy the #eq? predicate.
_IMPORT_QUERY_SRC = """
(import_statement source: (string (string_fragment) @specifier))
(export_statement source: (string (string_fragment) @specifier))
(call_expression
  function: (identifier) @_fn (#eq? @_fn "require")
  arguments: (arguments (string (string_fragment) @specifier)))
(call_expression
  function: (import)
  arguments: (arguments (string (string_fragment) @specifier)))
"""

if HAS_TREE_SITTER:
    _JS_QUERY = Query(_JS_LANGUAGE, _IMPORT_QUERY_SRC)
    _TS_QUERY = Query(_TS_LANGUAGE, _IMPORT_QUERY_SRC)
    _TSX_QUERY = Query(_TSX_LANGUAGE, _IMPORT_QUERY_SRC)


def extract_js_imports(source_code: str) -> list[str]:
    """Parse JavaScript source and return sorted, deduplicated import specifiers."""
    parser = Parser(_JS_LANGUAGE)
    tree = parser.parse(source_code.encode("utf-8"))
    return _collect_specifiers(_JS_QUERY, tree)


def extract_ts_imports(source_code: str, tsx: bool = False) -> list[str]:
    """Parse TypeScript source and return sorted, deduplicated import specifiers."""
    query = _TSX_QUERY if tsx else _TS_QUERY
    lang = _TSX_LANGUAGE if tsx else _TS_LANGUAGE
    parser = Parser(lang)
    tree = parser.parse(source_code.encode("utf-8"))
    return _collect_specifiers(query, tree)


def _collect_specifiers(query: Query, tree: object) -> list[str]:  # type: ignore[attr-defined]
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)  # type: ignore[attr-defined]
    specifiers: set[str] = set()
    for node in captures.get("specifier", []):
        if node.text:
            specifiers.add(node.text.decode("utf-8"))
    return sorted(specifiers)
