import re
from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

IMPORT_EXPORT_RE = re.compile(
    r"""\b(?:import|export)\s+(?:type\s+)?(?:[^"'()]*?\s+from\s+)?["']([^"']+)["']"""
)
REQUIRE_RE = re.compile(r"""\brequire\(\s*["']([^"']+)["']\s*\)""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*["']([^"']+)["']\s*\)""")


class JSParser(ParserPlugin):
    language = "javascript"
    extensions = [".js", ".jsx", ".mjs", ".cjs"]

    def parse(self, source_code: str) -> list[str]:
        from archmap.core.parser.ts_engine import HAS_TREE_SITTER, extract_js_imports

        if HAS_TREE_SITTER:
            return extract_js_imports(source_code)

        from archmap.core.parser._text import strip_comments

        cleaned = strip_comments(source_code, string_delims=('"', "'", "`"))
        imports: set[str] = set()
        for pattern in (IMPORT_EXPORT_RE, REQUIRE_RE, DYNAMIC_IMPORT_RE):
            for match in pattern.finditer(cleaned):
                specifier = match.group(1).strip()
                if specifier:
                    imports.add(specifier)
        return sorted(imports)

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str], **kwargs: Any
    ) -> list[Dependency]:
        from archmap.core.parser import _load_tsconfig_aliases, _resolve_js_ts_dependency

        aliases = _load_tsconfig_aliases(kwargs.get("get_file_content"))

        resolved: list[Dependency] = []
        for specifier in import_entries:
            if isinstance(specifier, str):
                dep = _resolve_js_ts_dependency(specifier, file_id, file_ids, aliases)
                if dep:
                    resolved.append(dep)
        return resolved
