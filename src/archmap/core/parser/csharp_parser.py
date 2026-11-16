from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

# Captures `using X;`, `global using X;`, `using static X;` and the right-hand
# side of alias directives `using Alias = Real.Namespace;`.
CS_IMPORT_RE = re.compile(
    r"^\s*(?:global\s+)?using\s+(?:static\s+)?(?:[A-Za-z_][\w.]*\s*=\s*)?([^;]+);",
    re.MULTILINE,
)


class CSharpParser(ParserPlugin):
    language = "csharp"
    extensions = [".cs"]

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser import ts_engine

        ts_result = ts_engine.try_extract("csharp", source_code)
        if ts_result is not None:
            return ts_result

        from archmap.core.parser._text import strip_comments

        cleaned = strip_comments(source_code)
        imports: set[str] = set()
        for match in CS_IMPORT_RE.finditer(cleaned):
            value = match.group(1).strip()
            # Skip `using (var x = ...)` resource statements and aliases to a
            # generic/type expression that are not namespace imports.
            if value and "(" not in value and not value.startswith("var "):
                imports.add(value)
        return sorted(imports)

    def resolve(
        self,
        import_entries: list[Any],
        file_id: str,
        file_ids: set[str],
        **kwargs: Any,
    ) -> list[Dependency]:
        from archmap.core.parser.csharp_index import index_for
        from archmap.core.parser.resolvers import (
            _make_file_dependency,
            _resolve_csharp_dependency,
        )

        usings = [_strip_static(e) for e in import_entries if isinstance(e, str)]
        index = index_for(file_ids, kwargs.get("get_file_content"))
        if index is None or file_id not in index.files:
            # No project view (e.g. a direct call without file access): fall
            # back to the namespace-directory heuristic.
            resolved: list[Dependency] = []
            for entry in usings:
                resolved.extend(_resolve_csharp_dependency(entry, file_id, file_ids))
            return resolved

        resolved = [
            _make_file_dependency(target)
            for target in sorted(index.dependencies_of(file_id, usings))
        ]
        for entry in usings:
            if not index.is_known(entry):
                resolved.extend(_resolve_csharp_dependency(entry, file_id, set()))
        return resolved

    def is_import_known(
        self, entry: Any, file_id: str, file_ids: set[str], **kwargs: Any
    ) -> bool:
        """A ``using`` of a project namespace is resolved even when it adds no edge."""
        from archmap.core.parser.csharp_index import index_for

        index = index_for(file_ids, kwargs.get("get_file_content"))
        return bool(index and isinstance(entry, str) and index.is_known(_strip_static(entry)))


def _strip_static(specifier: str) -> str:
    specifier = specifier.strip()
    return specifier[7:].strip() if specifier.startswith("static ") else specifier
