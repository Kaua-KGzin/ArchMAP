from __future__ import annotations

import re

IMPORT_EXPORT_RE = re.compile(
    r"""\b(?:import|export)\s+(?:type\s+)?(?:[^"'()]*?\s+from\s+)?["']([^"']+)["']"""
)
REQUIRE_RE = re.compile(r"""\brequire\(\s*["']([^"']+)["']\s*\)""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*["']([^"']+)["']\s*\)""")


def parse_js_imports(source_code: str) -> list[str]:
    imports: set[str] = set()

    for pattern in (IMPORT_EXPORT_RE, REQUIRE_RE, DYNAMIC_IMPORT_RE):
        for match in pattern.finditer(source_code):
            specifier = match.group(1).strip()
            if specifier:
                imports.add(specifier)

    return sorted(imports)
