from __future__ import annotations

import re
from typing import TypedDict


class PythonImportEntry(TypedDict):
    type: str
    module: str
    names: list[str]


IMPORT_RE = re.compile(r"^\s*import\s+([^\n#]+)$", re.MULTILINE)
FROM_RE = re.compile(r"^\s*from\s+([.a-zA-Z0-9_]+)\s+import\s+([^\n#]+)$", re.MULTILINE)


def parse_python_imports(source_code: str) -> list[PythonImportEntry]:
    source_code = source_code.lstrip("\ufeff")
    dependencies: list[PythonImportEntry] = []

    for match in IMPORT_RE.finditer(source_code):
        modules = _sanitize_import_part(match.group(1)).split(",")
        for raw_module in modules:
            module = raw_module.strip().split(" as ")[0].strip()
            if not module:
                continue
            dependencies.append({"type": "import", "module": module, "names": []})

    for match in FROM_RE.finditer(source_code):
        module = match.group(1).strip()
        names = [
            entry.strip().split(" as ")[0].strip()
            for entry in _sanitize_import_part(match.group(2)).split(",")
        ]
        names = [name for name in names if name]
        dependencies.append({"type": "from", "module": module, "names": names})

    return dependencies


def _sanitize_import_part(value: str) -> str:
    return value.split("#", maxsplit=1)[0].strip()
