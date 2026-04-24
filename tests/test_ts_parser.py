from __future__ import annotations

import pytest

from archmap.core.parser.ts_parser import TSParser


@pytest.fixture
def parser() -> TSParser:
    return TSParser()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_language_is_typescript(parser: TSParser) -> None:
    assert parser.language == "typescript"


def test_extensions(parser: TSParser) -> None:
    assert ".ts" in parser.extensions
    assert ".tsx" in parser.extensions
    assert ".mts" in parser.extensions
    assert ".cts" in parser.extensions


# ---------------------------------------------------------------------------
# Inherits JSParser import handling
# ---------------------------------------------------------------------------

def test_parses_es_import(parser: TSParser) -> None:
    src = "import { Component } from './component';"
    assert "./component" in parser.parse(src)


def test_parses_default_import(parser: TSParser) -> None:
    src = "import React from 'react';"
    assert "react" in parser.parse(src)


def test_parses_dynamic_import(parser: TSParser) -> None:
    src = "const mod = await import('./lazy-mod');"
    assert "./lazy-mod" in parser.parse(src)


def test_parses_export_from(parser: TSParser) -> None:
    src = "export { foo } from './utils';"
    assert "./utils" in parser.parse(src)


# ---------------------------------------------------------------------------
# TS-specific: import type
# ---------------------------------------------------------------------------

def test_parses_import_type(parser: TSParser) -> None:
    src = "import type { Foo } from './types';"
    assert "./types" in parser.parse(src)


def test_parses_export_type_from(parser: TSParser) -> None:
    src = "export type { Bar } from './bar-types';"
    assert "./bar-types" in parser.parse(src)


# ---------------------------------------------------------------------------
# TS-specific: triple-slash references
# ---------------------------------------------------------------------------

def test_triple_slash_path_reference(parser: TSParser) -> None:
    src = '/// <reference path="./globals.d.ts" />\nimport foo from "./foo";'
    result = parser.parse(src)
    assert "./globals.d.ts" in result
    assert "./foo" in result


def test_triple_slash_types_reference(parser: TSParser) -> None:
    src = '/// <reference types="node" />\n'
    assert "node" in parser.parse(src)


def test_multiple_triple_slash_references(parser: TSParser) -> None:
    src = (
        '/// <reference path="./a.d.ts" />\n'
        '/// <reference path="./b.d.ts" />\n'
        "import { x } from './c';\n"
    )
    result = parser.parse(src)
    assert "./a.d.ts" in result
    assert "./b.d.ts" in result
    assert "./c" in result


def test_triple_slash_after_code_is_ignored(parser: TSParser) -> None:
    # Triple-slash refs must appear before any statements; after code they're comments
    src = "const x = 1;\n/// <reference path='./skipped.d.ts' />\n"
    result = parser.parse(src)
    assert "./skipped.d.ts" not in result


def test_triple_slash_single_quotes(parser: TSParser) -> None:
    src = "/// <reference path='./single.d.ts' />\n"
    assert "./single.d.ts" in parser.parse(src)


def test_triple_slash_without_self_close(parser: TSParser) -> None:
    src = '/// <reference path="./no-close.d.ts">\n'
    assert "./no-close.d.ts" in parser.parse(src)


def test_no_triple_slash_in_normal_comment(parser: TSParser) -> None:
    src = "// not a reference directive\nimport x from './x';\n"
    result = parser.parse(src)
    assert "./x" in result


# ---------------------------------------------------------------------------
# Resolve — delegates to JSParser resolver
# ---------------------------------------------------------------------------

def test_resolve_external_package_yields_package_node(parser: TSParser) -> None:
    file_ids = {"src/a.ts", "src/b.ts"}
    result = parser.resolve(["react"], "src/a.ts", file_ids)
    assert len(result) == 1
    assert result[0]["type"] == "package"
    assert "react" in result[0]["id"]


def test_resolve_relative_file(parser: TSParser) -> None:
    file_ids = {"src/a.ts", "src/util.ts"}
    result = parser.resolve(["./util"], "src/a.ts", file_ids)
    assert len(result) == 1
    assert result[0]["id"] == "src/util.ts"
    assert result[0]["type"] == "file"
