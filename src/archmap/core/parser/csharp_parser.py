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
        from archmap.core.parser.resolvers import _resolve_csharp_dependency

        resolved: list[Dependency] = []
        for entry in import_entries:
            if isinstance(entry, str):
                resolved.extend(_resolve_csharp_dependency(entry, file_id, file_ids))
        return resolved
