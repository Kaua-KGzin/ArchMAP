from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

CS_IMPORT_RE = re.compile(r"^\s*using\s+([^=;]+);", re.MULTILINE)


class CSharpParser(ParserPlugin):
    language = "csharp"
    extensions = [".cs"]

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser.ts_engine import HAS_TREE_SITTER, extract_csharp_imports

        if HAS_TREE_SITTER:
            return extract_csharp_imports(source_code)

        imports: set[str] = set()
        for match in CS_IMPORT_RE.finditer(source_code):
            imports.add(match.group(1).strip())
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
