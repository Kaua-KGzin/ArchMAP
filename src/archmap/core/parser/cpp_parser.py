from __future__ import annotations

import re
from typing import Any, TypedDict

from archmap.core.parser.registry import Dependency, ParserPlugin

SYSTEM_INCLUDE_RE = re.compile(r"^\s*#include\s*<([^>]+)>", re.MULTILINE)
LOCAL_INCLUDE_RE = re.compile(r"^\s*#include\s*\"([^\"]+)\"", re.MULTILINE)


class CppImportEntry(TypedDict):
    type: str  # "system" or "local"
    value: str


def _parse_cpp_includes(source_code: str, cpp: bool = False) -> list[CppImportEntry]:
    from archmap.core.parser import ts_engine  # noqa: PLC0415

    ts_result = ts_engine.try_extract("cpp" if cpp else "c", source_code)
    if ts_result is not None:
        return ts_result

    from archmap.core.parser._text import strip_comments

    # `#` is a preprocessor directive in C/C++, not a comment, so only //-style
    # and block comments are stripped. String delims kept so #include "x" stays.
    source_code = strip_comments(source_code, line_comments=("//",))
    imports: list[CppImportEntry] = []
    for match in SYSTEM_INCLUDE_RE.finditer(source_code):
        imports.append({"type": "system", "value": match.group(1).strip()})
    for match in LOCAL_INCLUDE_RE.finditer(source_code):
        imports.append({"type": "local", "value": match.group(1).strip()})
    return imports


def _resolve_cpp_includes(
    import_entries: list[Any],
    file_id: str,
    file_ids: set[str],
) -> list[Dependency]:
    from archmap.core.parser.resolvers import _resolve_cpp_dependency

    resolved: list[Dependency] = []
    for entry in import_entries:
        if isinstance(entry, dict):
            resolved.extend(_resolve_cpp_dependency(entry, file_id, file_ids))
    return resolved


class CParser(ParserPlugin):
    language = "c"
    extensions = [".c", ".h"]

    def parse(self, source_code: str) -> list[CppImportEntry]:
        return _parse_cpp_includes(source_code)

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str], **kwargs: Any
    ) -> list[Dependency]:
        return _resolve_cpp_includes(import_entries, file_id, file_ids)


class CppParser(ParserPlugin):
    language = "cpp"
    extensions = [".cpp", ".hpp", ".cc", ".cxx"]

    def parse(self, source_code: str) -> list[CppImportEntry]:
        return _parse_cpp_includes(source_code, cpp=True)

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str], **kwargs: Any
    ) -> list[Dependency]:
        return _resolve_cpp_includes(import_entries, file_id, file_ids)
