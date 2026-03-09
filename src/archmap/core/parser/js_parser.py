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
        imports: set[str] = set()
        for pattern in (IMPORT_EXPORT_RE, REQUIRE_RE, DYNAMIC_IMPORT_RE):
            for match in pattern.finditer(source_code):
                specifier = match.group(1).strip()
                if specifier:
                    imports.add(specifier)
        return sorted(imports)

    def resolve(self, import_entries: list[Any], file_id: str, file_ids: set[str]) -> list[Dependency]:
        from archmap.core.parser import _resolve_js_ts_dependency
        resolved: list[Dependency] = []
        for specifier in import_entries:
            if isinstance(specifier, str):
                dep = _resolve_js_ts_dependency(specifier, file_id, file_ids)
                if dep:
                    resolved.append(dep)
        return resolved

class TSParser(JSParser):
    language = "typescript"
    extensions = [".ts", ".tsx", ".mts", ".cts"]
