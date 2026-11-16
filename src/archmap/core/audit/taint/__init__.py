"""Interprocedural taint analysis (TAINT-* findings) for `archmap audit`.

Tracks untrusted input (HTTP request data, URL/DOM in the browser, argv/stdin)
through assignments, string building and function calls — across files, using
the dependency graph to resolve callees — to dangerous sinks (SQL, shell,
eval, templates, file paths, outbound URLs, HTML, redirects). Python is lowered
from a real AST; JS/TS, C# and Java through a statement-level reader.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from archmap.core.audit.taint.clike_frontend import LANGUAGE_BY_EXT as _CLIKE_EXT
from archmap.core.audit.taint.clike_frontend import lower_clike
from archmap.core.audit.taint.model import SINKS, Function, SinkHit, Solver, build_resolver
from archmap.core.audit.taint.python_frontend import lower_python

SUPPORTED_EXTENSIONS = frozenset({".py", *_CLIKE_EXT})


def lower_file(file: str, source: str) -> list[Function]:
    source = source.removeprefix("\ufeff")  # BOM from Windows editors
    if file.endswith(".py"):
        return lower_python(file, source)
    return lower_clike(file, source)


def analyze_sources(
    sources: Mapping[str, str],
    neighbours: Callable[[str], set[str]] | None = None,
) -> list[SinkHit]:
    """Run taint analysis over ``{relative path: source}``.

    ``neighbours(file)`` returns the files ``file`` imports (from the
    dependency graph); callees are only resolved within that scope.
    """
    functions: list[Function] = []
    for file in sorted(sources):
        suffix = file[file.rfind("."):].lower() if "." in file else ""
        if suffix in SUPPORTED_EXTENSIONS:
            functions.extend(lower_file(file, sources[file]))
    scope = neighbours or (lambda _file: set())
    return Solver(functions, build_resolver(functions, scope)).run()


__all__ = ["SINKS", "SUPPORTED_EXTENSIONS", "SinkHit", "analyze_sources", "lower_file"]
