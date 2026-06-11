from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.js_parser import JSParser
from archmap.core.parser.registry import Dependency

# Matches: /// <reference path="..." /> and /// <reference types="..." />
_TRIPLE_SLASH_RE = re.compile(
    r"""///\s*<reference\s+(?:path|types)\s*=\s*["']([^"']+)["']\s*/?>""",
)


class TSParser(JSParser):
    """TypeScript parser extending JSParser with TS-specific constructs.

    Additions over JSParser:
    - Triple-slash reference directives (/// <reference path="..." />)
    - Explicit import type handling (import type { ... } from '...')
    """

    language = "typescript"
    extensions = [".ts", ".tsx", ".mts", ".cts"]
    # Use the TypeScript grammar directly rather than the JS grammar inherited
    # from JSParser — avoids misclassification of TS-specific syntax.
    _TS_LANGUAGE = "typescript"

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser import ts_engine

        ts_result = ts_engine.try_extract(self._TS_LANGUAGE, source_code)
        if ts_result is not None:
            imports = set(ts_result)
        else:
            imports = set(self._parse_with_regex(source_code))

        imports.update(self._parse_triple_slash_refs(source_code))
        return sorted(imports)

    # ------------------------------------------------------------------
    # Triple-slash references
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_triple_slash_refs(source_code: str) -> list[str]:
        """Extract specifiers from /// <reference path|types="..." /> directives."""
        refs: list[str] = []
        for line in source_code.splitlines():
            stripped = line.strip()
            if not stripped.startswith("///"):
                # Triple-slash directives must appear before any other statements
                break
            match = _TRIPLE_SLASH_RE.search(stripped)
            if match:
                refs.append(match.group(1))
        return refs

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str], **kwargs: Any
    ) -> list[Dependency]:
        return super().resolve(import_entries, file_id, file_ids, **kwargs)


__all__ = ["TSParser"]
