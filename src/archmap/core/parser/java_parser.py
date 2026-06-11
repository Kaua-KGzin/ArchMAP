from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([^;]+);", re.MULTILINE)


class JavaParser(ParserPlugin):
    language = "java"
    extensions = [".java"]

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser.ts_engine import HAS_TREE_SITTER, extract_java_imports

        if HAS_TREE_SITTER:
            return extract_java_imports(source_code)

        from archmap.core.parser._text import strip_comments

        cleaned = strip_comments(source_code)
        imports: set[str] = set()
        for match in JAVA_IMPORT_RE.finditer(cleaned):
            imports.add(match.group(1).strip())
        return sorted(imports)

    def resolve(
        self,
        import_entries: list[Any],
        file_id: str,
        file_ids: set[str],
        **kwargs: Any,
    ) -> list[Dependency]:
        from archmap.core.parser.resolvers import _resolve_java_dependency

        resolved: list[Dependency] = []
        for entry in import_entries:
            if isinstance(entry, str):
                resolved.extend(_resolve_java_dependency(entry, file_id, file_ids))
        return resolved
