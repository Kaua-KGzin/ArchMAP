import ast
import re
from typing import Any, TypedDict

from archmap.core.parser.registry import Dependency, ParserPlugin


class PythonImportEntry(TypedDict):
    type: str
    module: str
    names: list[str]


IMPORT_RE = re.compile(r"^\s*import\s+([^\n#]+)$", re.MULTILINE)
FROM_RE = re.compile(r"^\s*from\s+([.a-zA-Z0-9_]+)\s+import\s+([^\n#]+)$", re.MULTILINE)


class PythonParser(ParserPlugin):
    language = "python"
    extensions = [".py"]

    def parse(self, source_code: str) -> list[PythonImportEntry]:
        source_code = source_code.lstrip("\ufeff")
        try:
            return _parse_with_ast(source_code)
        except SyntaxError:
            return _parse_with_regex(source_code)

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str], **kwargs: Any
    ) -> list[Dependency]:
        from archmap.core.parser.resolvers import _resolve_python_dependency

        resolved: list[Dependency] = []
        for entry in import_entries:
            if isinstance(entry, dict):
                resolved.extend(_resolve_python_dependency(entry, file_id, file_ids))
        return resolved


def _parse_with_ast(source_code: str) -> list[PythonImportEntry]:
    dependencies: list[PythonImportEntry] = []
    tree = ast.parse(source_code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    dependencies.append({"type": "import", "module": alias.name, "names": []})
            continue

        if isinstance(node, ast.ImportFrom):
            module = f"{'.' * node.level}{node.module or ''}"
            names = [alias.name for alias in node.names if alias.name]
            if module:
                dependencies.append({"type": "from", "module": module, "names": names})

    return dependencies


def _parse_with_regex(source_code: str) -> list[PythonImportEntry]:
    dependencies: list[PythonImportEntry] = []
    for match in IMPORT_RE.finditer(source_code):
        modules = _sanitize_import_part(match.group(1)).split(",")
        for raw_module in modules:
            module = raw_module.strip().split(" as ")[0].strip()
            if module:
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
