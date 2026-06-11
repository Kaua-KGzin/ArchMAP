"""Tree-sitter engine for multi-language import extraction.

Design goals (v1.0.3):

- **Per-language availability.** Each grammar loads independently. If, say,
  ``tree-sitter-php`` is missing or fails to load, PHP transparently uses its
  regex fallback while every other language still benefits from tree-sitter.
- **Automatic per-file fallback.** ``try_extract`` is the entry point used by
  the parsers. It returns ``None`` whenever tree-sitter cannot be trusted for a
  given file — grammar unavailable, an exception during parse/query, or a parse
  that contains syntax errors *and* yielded no imports — so the caller switches
  to the regex path for that single file instead of dropping it.
- **Structured extraction.** Specifiers are read from typed AST nodes rather
  than by slicing the matched text, so aliases, ``global using``, ``static``,
  multiline imports, and string/comment noise are handled correctly.

Install the optional extra to enable: ``pip install archmap[tree-sitter]``.
"""
from __future__ import annotations

import logging
import re as _re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Populated lazily below: language name -> compiled tree_sitter.Language.
_LANGUAGES: dict[str, Any] = {}
# language name -> compiled Query objects (built once, on first availability).
_QUERIES: dict[str, Any] = {}

_Language: Any = None
_Parser: Any = None
_Query: Any = None
_QueryCursor: Any = None

try:
    from tree_sitter import Language, Parser, Query, QueryCursor

    _Language, _Parser, _Query, _QueryCursor = Language, Parser, Query, QueryCursor
    _TS_CORE_AVAILABLE = True
except ImportError:
    _TS_CORE_AVAILABLE = False


# Each grammar is imported in isolation: one missing wheel does not disable the
# rest. ``language_constructor`` returns the raw grammar pointer.
_GRAMMAR_LOADERS: dict[str, tuple[str, str]] = {
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "java": ("tree_sitter_java", "language"),
    "go": ("tree_sitter_go", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "php": ("tree_sitter_php", "language_php"),
    "csharp": ("tree_sitter_c_sharp", "language"),
    "c": ("tree_sitter_c", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
}


def _load_language(name: str) -> Any | None:
    if not _TS_CORE_AVAILABLE:
        return None
    if name in _LANGUAGES:
        return _LANGUAGES[name]
    spec = _GRAMMAR_LOADERS.get(name)
    if spec is None:
        return None
    module_name, attr = spec
    try:
        module = __import__(module_name)
        language = _Language(getattr(module, attr)())
    except (ImportError, AttributeError, ValueError, TypeError) as exc:
        logger.debug("tree-sitter grammar %s unavailable: %s", name, exc)
        return None
    _LANGUAGES[name] = language
    return language


def language_available(name: str) -> bool:
    """Return True if a usable tree-sitter grammar is loaded for ``name``."""
    return _load_language(name) is not None


# Eagerly probe every grammar so HAS_TREE_SITTER reflects real availability and
# query objects are built once up front (cheaper than per-call).
for _lang_name in _GRAMMAR_LOADERS:
    _load_language(_lang_name)

HAS_TREE_SITTER = bool(_LANGUAGES)


# ---------------------------------------------------------------------------
# Query strings
# ---------------------------------------------------------------------------

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
_PHP_REQUIRE_QUERY_SRC = "[(require_expression) @req (require_once_expression) @req]"
_PHP_INCLUDE_QUERY_SRC = "[(include_expression) @inc (include_once_expression) @inc]"

_CS_QUERY_SRC = "(using_directive) @decl"

_INCLUDE_QUERY_SRC = "(preproc_include) @inc"


def _query(language_name: str, key: str, source: str) -> Any | None:
    """Lazily compile and cache a Query for a language."""
    cache_key = f"{language_name}:{key}"
    if cache_key in _QUERIES:
        return _QUERIES[cache_key]
    language = _load_language(language_name)
    if language is None:
        return None
    try:
        compiled = _Query(language, source)
    except Exception as exc:  # noqa: BLE001 - grammar/query mismatch -> fall back
        logger.debug("tree-sitter query compile failed for %s/%s: %s", language_name, key, exc)
        _QUERIES[cache_key] = None
        return None
    _QUERIES[cache_key] = compiled
    return compiled


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _captures(query: Any, tree: Any) -> dict[str, list]:
    """Run a query and return captures sorted by document position."""
    cursor = _QueryCursor(query)
    raw = cursor.captures(tree.root_node)
    if isinstance(raw, dict):
        return {
            k: sorted(v, key=lambda n: (n.start_point.row, n.start_point.column))
            for k, v in raw.items()
        }
    result: dict[str, list] = {}
    for node, name in raw:
        result.setdefault(name, []).append(node)
    return result


def _parse(language: Any, source_code: str) -> Any:
    return _Parser(language).parse(source_code.encode("utf-8"))


def _text(node: Any) -> str:
    raw = getattr(node, "text", None)
    return raw.decode("utf-8") if raw else ""


def _find_string_content(node: Any) -> str | None:
    if getattr(node, "type", "") == "string_content":
        return _text(node)
    for child in getattr(node, "named_children", []):
        result = _find_string_content(child)
        if result is not None:
            return result
    return None


def _last_name_node(node: Any) -> Any | None:
    """Return the last identifier/qualified-name child (the real namespace).

    For ``using Alias = Real.Ns;`` the alias identifier comes first and the
    namespace second, so the last name node is the import target.
    """
    name_types = {"identifier", "qualified_name", "alias_qualified_name"}
    chosen = None
    for child in getattr(node, "named_children", []):
        if getattr(child, "type", "") in name_types:
            chosen = child
    return chosen


# ---------------------------------------------------------------------------
# Per-language extraction from an already-parsed tree
# ---------------------------------------------------------------------------

def _extract_js_from_tree(tree: Any, language_name: str) -> list[str]:
    query = _query(language_name, "imports", _JS_QUERY_SRC)
    if query is None:
        return []
    specifiers: set[str] = set()
    for node in _captures(query, tree).get("specifier", []):
        val = _text(node)
        if val:
            specifiers.add(val)
    return sorted(specifiers)


def _extract_java_from_tree(tree: Any) -> list[str]:
    query = _query("java", "imports", _JAVA_QUERY_SRC)
    if query is None:
        return []
    results: set[str] = set()
    for node in _captures(query, tree).get("decl", []):
        raw = _text(node).strip().removeprefix("import ").removeprefix("static ")
        val = raw.removesuffix(";").strip()
        if val:
            results.add(val)
    return sorted(results)


def _extract_go_from_tree(tree: Any) -> list[str]:
    query = _query("go", "imports", _GO_QUERY_SRC)
    if query is None:
        return []
    results: set[str] = set()
    for node in _captures(query, tree).get("path", []):
        val = _text(node)
        if val:
            results.add(val)
    return sorted(results)


def _extract_rust_from_tree(tree: Any) -> list[dict]:
    results: list[dict] = []
    use_q = _query("rust", "use", _RUST_USE_QUERY_SRC)
    mod_q = _query("rust", "mod", _RUST_MOD_QUERY_SRC)
    extern_q = _query("rust", "extern", _RUST_EXTERN_QUERY_SRC)
    if use_q is not None:
        for node in _captures(use_q, tree).get("arg", []):
            normalized = _normalize_rust_use(_text(node))
            if normalized:
                results.append({"type": "use", "path": normalized, "module": "", "crate": ""})
    if mod_q is not None:
        for node in _captures(mod_q, tree).get("name", []):
            val = _text(node)
            if val:
                results.append({"type": "mod", "path": "", "module": val, "crate": ""})
    if extern_q is not None:
        for node in _captures(extern_q, tree).get("name", []):
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


def _extract_php_from_tree(tree: Any) -> list[dict]:
    results: list[dict] = []
    use_q = _query("php", "use", _PHP_USE_QUERY_SRC)
    req_q = _query("php", "require", _PHP_REQUIRE_QUERY_SRC)
    inc_q = _query("php", "include", _PHP_INCLUDE_QUERY_SRC)
    if use_q is not None:
        for node in _captures(use_q, tree).get("decl", []):
            val = _text(node).strip().removeprefix("use ").removesuffix(";").strip()
            if val:
                results.append({"type": "use", "value": val})
    if req_q is not None:
        for node in _captures(req_q, tree).get("req", []):
            val_r = _find_string_content(node)
            if val_r:
                results.append({"type": "require", "value": val_r})
    if inc_q is not None:
        for node in _captures(inc_q, tree).get("inc", []):
            val_i = _find_string_content(node)
            if val_i:
                results.append({"type": "include", "value": val_i})
    return results


def _extract_csharp_from_tree(tree: Any) -> list[str]:
    query = _query("csharp", "imports", _CS_QUERY_SRC)
    if query is None:
        return []
    results: set[str] = set()
    for node in _captures(query, tree).get("decl", []):
        name_node = _last_name_node(node)
        # Skip `using (var x = ...)` resource statements (no name child).
        val = _text(name_node).strip() if name_node is not None else ""
        if val:
            results.add(val)
    return sorted(results)


def _extract_includes_from_tree(tree: Any, language_name: str) -> list[dict]:
    query = _query(language_name, "include", _INCLUDE_QUERY_SRC)
    if query is None:
        return []
    results: list[dict] = []
    for inc_node in _captures(query, tree).get("inc", []):
        for child in inc_node.children:
            if getattr(child, "type", "") == "system_lib_string":
                raw = _text(child)
                results.append({"type": "system", "value": raw[1:-1]})
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


# ---------------------------------------------------------------------------
# Orchestration: parse + reliability check + automatic fallback
# ---------------------------------------------------------------------------

# language name -> (grammar key, extractor taking (tree, grammar_name)).
_EXTRACTORS: dict[str, tuple[str, Callable[[Any, str], Any]]] = {
    "javascript": ("javascript", lambda t, n: _extract_js_from_tree(t, "javascript")),
    "typescript": ("typescript", lambda t, n: _extract_js_from_tree(t, "typescript")),
    "tsx": ("tsx", lambda t, n: _extract_js_from_tree(t, "tsx")),
    "java": ("java", lambda t, n: _extract_java_from_tree(t)),
    "go": ("go", lambda t, n: _extract_go_from_tree(t)),
    "rust": ("rust", lambda t, n: _extract_rust_from_tree(t)),
    "php": ("php", lambda t, n: _extract_php_from_tree(t)),
    "csharp": ("csharp", lambda t, n: _extract_csharp_from_tree(t)),
    "c": ("c", lambda t, n: _extract_includes_from_tree(t, "c")),
    "cpp": ("cpp", lambda t, n: _extract_includes_from_tree(t, "cpp")),
}


def try_extract(language: str, source_code: str) -> Any | None:
    """Extract imports via tree-sitter, or return ``None`` to request fallback.

    ``None`` is returned when tree-sitter must not be trusted for this file:
    the grammar is unavailable, parsing/querying raised, or the source has
    syntax errors *and* no imports were recovered. In every other case the
    structured tree-sitter result is returned (possibly an empty list, which is
    a legitimate "no imports" answer for a cleanly-parsed file).
    """
    spec = _EXTRACTORS.get(language)
    if spec is None:
        return None
    grammar_name, extractor = spec
    grammar = _load_language(grammar_name)
    if grammar is None:
        return None

    try:
        tree = _parse(grammar, source_code)
        entries = extractor(tree, grammar_name)
    except Exception as exc:  # noqa: BLE001 - any failure -> regex fallback
        logger.debug("tree-sitter extraction failed for %s: %s", language, exc)
        return None

    # A parse with errors that recovered nothing is unreliable: let the
    # comment-aware regex fallback try instead of silently losing imports.
    if not entries and _tree_has_error(tree):
        return None
    return entries


def _tree_has_error(tree: Any) -> bool:
    root = getattr(tree, "root_node", None)
    return bool(getattr(root, "has_error", False)) if root is not None else False


# ---------------------------------------------------------------------------
# Backwards-compatible public extractors (used directly by tests)
# ---------------------------------------------------------------------------

def extract_js_imports(source_code: str) -> list[str]:
    return _extract_js_from_tree(_parse(_load_language("javascript"), source_code), "javascript")


def extract_ts_imports(source_code: str, tsx: bool = False) -> list[str]:
    name = "tsx" if tsx else "typescript"
    return _extract_js_from_tree(_parse(_load_language(name), source_code), name)


def extract_java_imports(source_code: str) -> list[str]:
    return _extract_java_from_tree(_parse(_load_language("java"), source_code))


def extract_go_imports(source_code: str) -> list[str]:
    return _extract_go_from_tree(_parse(_load_language("go"), source_code))


def extract_rust_imports(source_code: str) -> list[dict]:
    return _extract_rust_from_tree(_parse(_load_language("rust"), source_code))


def extract_php_imports(source_code: str) -> list[dict]:
    return _extract_php_from_tree(_parse(_load_language("php"), source_code))


def extract_csharp_imports(source_code: str) -> list[str]:
    return _extract_csharp_from_tree(_parse(_load_language("csharp"), source_code))


def extract_c_includes(source_code: str) -> list[dict]:
    return _extract_includes_from_tree(_parse(_load_language("c"), source_code), "c")


def extract_cpp_includes(source_code: str) -> list[dict]:
    return _extract_includes_from_tree(_parse(_load_language("cpp"), source_code), "cpp")
