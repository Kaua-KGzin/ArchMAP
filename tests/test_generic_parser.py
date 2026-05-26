"""Tests for GenericParser — regex-based parser for Go, PHP, Java, C#, etc."""

from __future__ import annotations

import re

from archmap.core.parser.generic_parser import GenericParser


def _make_parser(patterns: list[str], prefix: str = "pkg:") -> GenericParser:
    return GenericParser(
        language="test",
        extensions=[".test"],
        patterns=[re.compile(p, re.MULTILINE) for p in patterns],
        package_prefix=prefix,
    )


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------


def test_parse_single_match() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'])
    result = parser.parse('import "fmt"')
    assert result == ["fmt"]


def test_parse_multiple_matches_deduplicated() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'])
    code = 'import "fmt"\nimport "os"\nimport "fmt"'
    result = parser.parse(code)
    assert result == ["fmt", "os"]


def test_parse_multiple_patterns() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"', r"require\s+'([^']+)'"])
    code = 'import "fmt"\nrequire \'lodash\''
    result = parser.parse(code)
    assert "fmt" in result
    assert "lodash" in result


def test_parse_empty_code() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'])
    assert parser.parse("") == []


def test_parse_no_match() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'])
    assert parser.parse("// no imports here") == []


def test_parse_strips_whitespace() -> None:
    parser = _make_parser([r'import\s+"( [^"]+ )"'])
    result = parser.parse('import " fmt "')
    assert result == ["fmt"]


def test_parse_returns_sorted() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'])
    code = 'import "zzz"\nimport "aaa"\nimport "mmm"'
    result = parser.parse(code)
    assert result == sorted(result)


# ---------------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------------


def test_resolve_basic() -> None:
    parser = _make_parser([r'import\s+"([^"]+)"'], prefix="pkg:")
    deps = parser.resolve(["fmt", "os"], "main.go", set())
    ids = [d["id"] for d in deps]
    assert "pkg:fmt" in ids
    assert "pkg:os" in ids


def test_resolve_type_is_package() -> None:
    parser = _make_parser([])
    deps = parser.resolve(["fmt"], "main.go", set())
    assert deps[0]["type"] == "package"


def test_resolve_label_is_specifier() -> None:
    parser = _make_parser([])
    deps = parser.resolve(["encoding/json"], "main.go", set())
    assert deps[0]["label"] == "encoding/json"


def test_resolve_custom_prefix() -> None:
    parser = _make_parser([], prefix="go:")
    deps = parser.resolve(["fmt"], "main.go", set())
    assert deps[0]["id"] == "go:fmt"


def test_resolve_skips_non_strings() -> None:
    parser = _make_parser([])
    deps = parser.resolve([123, None, "valid"], "main.go", set())  # type: ignore[list-item]
    assert len(deps) == 1
    assert deps[0]["label"] == "valid"


def test_resolve_empty_list() -> None:
    parser = _make_parser([])
    assert parser.resolve([], "main.go", set()) == []


# ---------------------------------------------------------------------------
# language / extensions metadata
# ---------------------------------------------------------------------------


def test_language_attribute() -> None:
    parser = GenericParser("go", [".go"], [])
    assert parser.language == "go"
    assert parser.extensions == [".go"]
