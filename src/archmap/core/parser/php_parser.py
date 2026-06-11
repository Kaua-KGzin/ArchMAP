from __future__ import annotations

import json
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
        from archmap.core.parser import ts_engine

        ts_result = ts_engine.try_extract("php", source_code)
        if ts_result is not None:
            return ts_result

        from archmap.core.parser._text import strip_comments

        source_code = strip_comments(
            source_code, line_comments=("//", "#"), string_delims=('"', "'")
        )
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

        psr4 = _load_composer_psr4(kwargs.get("get_file_content"))

        resolved: list[Dependency] = []
        for entry in import_entries:
            if isinstance(entry, dict):
                deps = _resolve_php_dependency(entry, file_id, file_ids, psr4)
                resolved.extend(deps)
        return resolved


def _load_composer_psr4(get_file_content: Any) -> dict[str, list[str]]:
    """Read composer.json and return its PSR-4 namespace -> directory map."""
    if not get_file_content:
        return {}
    raw = get_file_content("composer.json")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}

    psr4: dict[str, list[str]] = {}
    for section in ("autoload", "autoload-dev"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        mapping = block.get("psr-4")
        if not isinstance(mapping, dict):
            continue
        for prefix, target in mapping.items():
            if not isinstance(prefix, str):
                continue
            dirs = target if isinstance(target, list) else [target]
            string_dirs = [d for d in dirs if isinstance(d, str)]
            if string_dirs:
                psr4[prefix] = string_dirs
    return psr4
