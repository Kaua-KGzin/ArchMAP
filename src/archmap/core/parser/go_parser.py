from __future__ import annotations

import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

SINGLE_IMPORT_RE = re.compile(
    r'^\s*import\s+(?:(?:[A-Za-z_][A-Za-z0-9_]*|\.|_)\s+)?"([^"]+)"',
    re.MULTILINE,
)
BLOCK_IMPORT_RE = re.compile(
    r"^\s*import\s*\((.*?)\)",
    re.MULTILINE | re.DOTALL,
)
BLOCK_ENTRY_RE = re.compile(
    r'^\s*(?:(?:[A-Za-z_][A-Za-z0-9_]*|\.|_)\s+)?"([^"]+)"',
    re.MULTILINE,
)


class GoParser(ParserPlugin):
    language = "go"
    extensions = [".go"]

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser import ts_engine

        ts_result = ts_engine.try_extract("go", source_code)
        if ts_result is not None:
            return ts_result

        imports: set[str] = set()

        for match in SINGLE_IMPORT_RE.finditer(source_code):
            specifier = match.group(1).strip()
            if specifier:
                imports.add(specifier)

        for block_match in BLOCK_IMPORT_RE.finditer(source_code):
            block_content = block_match.group(1)
            for entry_match in BLOCK_ENTRY_RE.finditer(block_content):
                specifier = entry_match.group(1).strip()
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
        from archmap.core.parser.resolvers import _resolve_go_dependency

        module_name = None
        replacements: dict[str, str] = {}
        get_file_content = kwargs.get("get_file_content")
        if get_file_content:
            mod_content = get_file_content("go.mod")
            if mod_content:
                match = re.search(r"^module\s+(.+)$", mod_content, re.MULTILINE)
                if match:
                    module_name = match.group(1).strip()
                replacements = _parse_go_replacements(mod_content)
        return _resolve_go_dependency(
            import_entries, file_id, file_ids, module_name, replacements
        )


# Matches a single replace mapping, with optional version on either side:
#   example.com/old => ./local
#   example.com/old v1.2.3 => ../local v0.0.0
_GO_REPLACE_RE = re.compile(
    r"^\s*(?:replace\s+)?([^\s=]+)(?:\s+v[^\s]+)?\s*=>\s*([^\s]+)",
    re.MULTILINE,
)


def _parse_go_replacements(mod_content: str) -> dict[str, str]:
    """Return a map of replaced module path -> local target path.

    Only local replacements (targets starting with ./ or ../) are kept; remote
    replacements still resolve as external packages.
    """
    replacements: dict[str, str] = {}
    for match in _GO_REPLACE_RE.finditer(mod_content):
        old, target = match.group(1).strip(), match.group(2).strip()
        if "=>" in old or not target:
            continue
        if target.startswith(("./", "../")):
            replacements[old] = target
    return replacements
