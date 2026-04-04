from __future__ import annotations

import re
from typing import Any, TypedDict

from archmap.core.parser.registry import Dependency, ParserPlugin

USE_RE = re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE)
REQUIRE_RE = re.compile(r"^\s*require(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
INCLUDE_RE = re.compile(r"^\s*include(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


class PHPImportEntry(TypedDict):
    type: str
    value: str


class PHPParser(ParserPlugin):
    language = "php"
    extensions = [".php"]

    def parse(self, source_code: str) -> list[PHPImportEntry]:
        imports: list[PHPImportEntry] = []
        for match in USE_RE.finditer(source_code):
            imports.append({"type": "use", "value": match.group(1).strip()})
        for match in REQUIRE_RE.finditer(source_code):
            imports.append({"type": "require", "value": match.group(1).strip()})
        for match in INCLUDE_RE.finditer(source_code):
            imports.append({"type": "include", "value": match.group(1).strip()})
        return imports

    def resolve(
        self,
        import_entries: list[Any],
        file_id: str,
        file_ids: set[str],
        **kwargs: Any,
    ) -> list[Dependency]:
        from archmap.core.parser.resolvers import _resolve_php_dependency

        resolved: list[Dependency] = []
        for entry in import_entries:
            if isinstance(entry, dict):
                deps = _resolve_php_dependency(entry, file_id, file_ids)
                resolved.extend(deps)
        return resolved
