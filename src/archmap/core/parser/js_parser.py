from __future__ import annotations

from typing import Any

from archmap.core.parser.registry import Dependency, ParserPlugin

STRING_QUOTES = {'"', "'"}
TEMPLATE_QUOTE = "`"
STATEMENT_TERMINATORS = {";"}
OPENING_DELIMITERS = {"(", "{", "["}
CLOSING_DELIMITERS = {
    ")": "(",
    "}": "{",
    "]": "[",
}
REGEX_PREFIX_CHARS = {
    "",
    "(",
    "[",
    "{",
    ",",
    ";",
    ":",
    "=",
    "!",
    "?",
    "&",
    "|",
    "^",
    "~",
    "+",
    "-",
    "*",
    "%",
    "<",
    ">",
}
REGEX_PREFIX_KEYWORDS = {
    "await",
    "case",
    "delete",
    "in",
    "instanceof",
    "new",
    "return",
    "throw",
    "typeof",
    "void",
    "yield",
}


class JSParser(ParserPlugin):
    language = "javascript"
    extensions = [".js", ".jsx", ".mjs", ".cjs"]

    def parse(self, source_code: str) -> list[str]:
        imports: set[str] = set()
        index = 0

        while index < len(source_code):
            index = _skip_whitespace_and_comments(source_code, index)
            if index >= len(source_code):
                break

            char = source_code[index]
            if char in STRING_QUOTES:
                _, index = _read_string_literal(source_code, index)
                continue
            if char == TEMPLATE_QUOTE:
                index = _skip_template_literal(source_code, index)
                continue
            if char == "/" and _can_start_regex_literal(source_code, index):
                index = _skip_regex_literal(source_code, index)
                continue

            identifier, next_index = _read_identifier(source_code, index)
            if identifier == "import":
                specifier, index = _parse_import_statement(source_code, next_index)
                if specifier:
                    imports.add(specifier)
                continue

            if identifier == "export":
                specifier, index = _parse_export_statement(source_code, next_index)
                if specifier:
                    imports.add(specifier)
                continue

            if identifier == "require":
                specifier, index = _parse_require_call(source_code, index, next_index)
                if specifier:
                    imports.add(specifier)
                continue

            index = next_index if identifier else index + 1

        return sorted(imports)

    def resolve(
        self, import_entries: list[Any], file_id: str, file_ids: set[str]
    ) -> list[Dependency]:
        from archmap.core.parser.resolvers import _resolve_js_ts_dependency

        resolved: list[Dependency] = []
        for specifier in import_entries:
            if isinstance(specifier, str):
                dep = _resolve_js_ts_dependency(specifier, file_id, file_ids)
                if dep:
                    resolved.append(dep)
        return resolved


def _parse_import_statement(source_code: str, index: int) -> tuple[str | None, int]:
    index = _skip_whitespace_and_comments(source_code, index)
    if index >= len(source_code):
        return None, index

    if source_code[index] == ".":
        return None, index + 1

    if source_code[index] == "(":
        return _parse_string_call_arguments(source_code, index)

    if source_code[index] in STRING_QUOTES:
        return _read_string_literal(source_code, index)

    from_index, end_index = _find_keyword_before_statement_end(source_code, index, "from")
    if from_index is None:
        return None, end_index

    string_index = _skip_whitespace_and_comments(source_code, from_index)
    if string_index >= len(source_code):
        return None, string_index

    if source_code[string_index] in STRING_QUOTES:
        return _read_string_literal(source_code, string_index)

    return None, string_index


def _parse_export_statement(source_code: str, index: int) -> tuple[str | None, int]:
    index = _skip_whitespace_and_comments(source_code, index)
    if index >= len(source_code):
        return None, index

    if source_code[index] not in {"*", "{"}:
        identifier, identifier_end = _read_identifier(source_code, index)
        if identifier != "type":
            return None, identifier_end if identifier else index + 1

    from_index, end_index = _find_keyword_before_statement_end(source_code, index, "from")
    if from_index is None:
        return None, end_index

    string_index = _skip_whitespace_and_comments(source_code, from_index)
    if string_index >= len(source_code):
        return None, string_index

    if source_code[string_index] in STRING_QUOTES:
        return _read_string_literal(source_code, string_index)

    return None, string_index


def _parse_require_call(source_code: str, index: int, next_index: int) -> tuple[str | None, int]:
    previous_significant = _previous_significant_char(source_code, index)
    if previous_significant == ".":
        return None, next_index

    return _parse_string_call_arguments(source_code, next_index)


def _parse_string_call_arguments(source_code: str, index: int) -> tuple[str | None, int]:
    index = _skip_whitespace_and_comments(source_code, index)
    if index >= len(source_code) or source_code[index] != "(":
        return None, index

    index = _skip_whitespace_and_comments(source_code, index + 1)
    if index >= len(source_code):
        return None, index

    if source_code[index] in STRING_QUOTES:
        return _read_string_literal(source_code, index)
    if source_code[index] == TEMPLATE_QUOTE:
        return _read_static_template_literal(source_code, index)

    return None, index


def _find_keyword_before_statement_end(
    source_code: str, index: int, keyword: str
) -> tuple[int | None, int]:
    depths = {delimiter: 0 for delimiter in OPENING_DELIMITERS}

    while index < len(source_code):
        index = _skip_whitespace_and_comments(source_code, index)
        if index >= len(source_code):
            return None, index

        char = source_code[index]
        if char in STRING_QUOTES:
            _, index = _read_string_literal(source_code, index)
            continue
        if char == TEMPLATE_QUOTE:
            index = _skip_template_literal(source_code, index)
            continue
        if char == "/" and _can_start_regex_literal(source_code, index):
            index = _skip_regex_literal(source_code, index)
            continue

        if char in STATEMENT_TERMINATORS and _at_depth_zero(depths):
            return None, index + 1
        if char in OPENING_DELIMITERS:
            depths[char] += 1
            index += 1
            continue
        if char in CLOSING_DELIMITERS:
            opener = CLOSING_DELIMITERS[char]
            depths[opener] = max(0, depths[opener] - 1)
            index += 1
            continue

        if _at_depth_zero(depths):
            identifier, next_index = _read_identifier(source_code, index)
            if identifier == keyword:
                return next_index, next_index
            if identifier:
                index = next_index
                continue

        index += 1

    return None, index


def _skip_whitespace_and_comments(source_code: str, index: int) -> int:
    while index < len(source_code):
        char = source_code[index]
        if char.isspace():
            index += 1
            continue

        if source_code.startswith("//", index):
            index += 2
            while index < len(source_code) and source_code[index] not in "\r\n":
                index += 1
            continue

        if source_code.startswith("/*", index):
            closing_index = source_code.find("*/", index + 2)
            if closing_index == -1:
                return len(source_code)
            index = closing_index + 2
            continue

        break

    return index


def _read_string_literal(source_code: str, index: int) -> tuple[str | None, int]:
    quote = source_code[index]
    index += 1
    chars: list[str] = []

    while index < len(source_code):
        char = source_code[index]
        if char == "\\":
            if index + 1 < len(source_code):
                chars.append(source_code[index + 1])
                index += 2
                continue
            return None, len(source_code)
        if char == quote:
            return "".join(chars), index + 1
        chars.append(char)
        index += 1

    return None, len(source_code)


def _read_static_template_literal(source_code: str, index: int) -> tuple[str | None, int]:
    start_index = index
    index += 1
    chars: list[str] = []

    while index < len(source_code):
        char = source_code[index]
        if char == "\\":
            if index + 1 < len(source_code):
                chars.append(source_code[index + 1])
                index += 2
                continue
            return None, len(source_code)
        if char == TEMPLATE_QUOTE:
            return "".join(chars), index + 1
        if char == "$" and index + 1 < len(source_code) and source_code[index + 1] == "{":
            return None, _skip_template_literal(source_code, start_index)
        chars.append(char)
        index += 1

    return None, len(source_code)


def _skip_template_literal(source_code: str, index: int) -> int:
    index += 1

    while index < len(source_code):
        char = source_code[index]
        if char == "\\":
            index += 2
            continue
        if char == TEMPLATE_QUOTE:
            return index + 1
        if char == "$" and index + 1 < len(source_code) and source_code[index + 1] == "{":
            index = _skip_template_expression(source_code, index + 2)
            continue
        index += 1

    return len(source_code)


def _skip_template_expression(source_code: str, index: int) -> int:
    depth = 1

    while index < len(source_code) and depth > 0:
        index = _skip_whitespace_and_comments(source_code, index)
        if index >= len(source_code):
            return index

        char = source_code[index]
        if char in STRING_QUOTES:
            _, index = _read_string_literal(source_code, index)
            continue
        if char == TEMPLATE_QUOTE:
            index = _skip_template_literal(source_code, index)
            continue
        if char == "/" and _can_start_regex_literal(source_code, index):
            index = _skip_regex_literal(source_code, index)
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            continue

        index += 1

    return index


def _skip_regex_literal(source_code: str, index: int) -> int:
    index += 1
    in_character_class = False

    while index < len(source_code):
        char = source_code[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            in_character_class = True
            index += 1
            continue
        if char == "]" and in_character_class:
            in_character_class = False
            index += 1
            continue
        if char == "/" and not in_character_class:
            index += 1
            while index < len(source_code) and _is_identifier_part(source_code[index]):
                index += 1
            return index
        index += 1

    return len(source_code)


def _can_start_regex_literal(source_code: str, index: int) -> bool:
    previous_significant = _previous_significant_char(source_code, index)
    if previous_significant in REGEX_PREFIX_CHARS:
        return True

    previous_identifier = _previous_identifier(source_code, index)
    return previous_identifier in REGEX_PREFIX_KEYWORDS


def _at_depth_zero(depths: dict[str, int]) -> bool:
    return all(depth == 0 for depth in depths.values())


def _read_identifier(source_code: str, index: int) -> tuple[str, int]:
    if index >= len(source_code) or not _is_identifier_start(source_code[index]):
        return "", index

    start = index
    index += 1
    while index < len(source_code) and _is_identifier_part(source_code[index]):
        index += 1

    return source_code[start:index], index


def _previous_significant_char(source_code: str, index: int) -> str:
    index -= 1
    while index >= 0:
        if not source_code[index].isspace():
            return source_code[index]
        index -= 1
    return ""


def _previous_identifier(source_code: str, index: int) -> str:
    index -= 1
    while index >= 0 and source_code[index].isspace():
        index -= 1
    if index < 0 or not _is_identifier_part(source_code[index]):
        return ""

    end = index + 1
    while index >= 0 and _is_identifier_part(source_code[index]):
        index -= 1
    return source_code[index + 1 : end]


def _is_identifier_start(char: str) -> bool:
    return char.isalpha() or char in {"_", "$"}


def _is_identifier_part(char: str) -> bool:
    return char.isalnum() or char in {"_", "$"}
