from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin


class GenericParser(ParserPlugin):
    """
    A reusable regex-based parser for languages with simple import patterns.
    (Go, PHP, Java, C#, C, C++)
    """

    def __init__(
        self,
        language: str,
        extensions: list[str],
        patterns: list[re.Pattern],
        package_prefix: str = "pkg:",
    ):
        self.language = language
        self.extensions = extensions
        self.patterns = patterns
        self.package_prefix = package_prefix

    def parse(self, source_code: str) -> list[str]:
        imports: set[str] = set()
        for pattern in self.patterns:
            for match in pattern.finditer(source_code):
                specifier = match.group(1).strip()
                if specifier:
                    imports.add(specifier)
        return sorted(imports)

    def resolve(
        self,
        import_entries: list[Any],
        file_id: str,
        file_ids: set[str],
        **kwargs: Any,
    ) -> list[Dependency]:
        # Minimal resolution logic for generic languages:
        # Treat everything as a potential package unless we want to add local path resolution later.
        dependencies: list[Dependency] = []
        for specifier in import_entries:
            if not isinstance(specifier, str):
                continue

            # In generic languages, we usually just want to know what's imported.
            # Local resolution can be added per-language if needed.
            dependencies.append(
                {
                    "id": f"{self.package_prefix}{specifier}",
                    "label": specifier,
                    "type": "package",
                }
            )
        return dependencies
