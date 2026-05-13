"""Tests for the tree-sitter JS/TS engine.

All tests are skipped when tree-sitter dependencies are not installed.
The suite deliberately covers cases where the regex fallback is known to
produce false positives or miss imports entirely.
"""
from __future__ import annotations

import pytest

ts_engine = pytest.importorskip(
    "archmap.core.parser.ts_engine",
    reason="tree-sitter packages not installed (pip install archmap[tree-sitter])",
)
pytestmark = pytest.mark.skipif(
    not ts_engine.HAS_TREE_SITTER,
    reason="tree-sitter packages not installed",
)


# ---------------------------------------------------------------------------
# JavaScript — basic coverage
# ---------------------------------------------------------------------------


def test_js_esm_import() -> None:
    src = "import express from 'express';"
    assert "express" in ts_engine.extract_js_imports(src)


def test_js_named_import() -> None:
    src = "import { foo, bar } from './utils';"
    assert "./utils" in ts_engine.extract_js_imports(src)


def test_js_side_effect_import() -> None:
    src = "import './polyfill';"
    assert "./polyfill" in ts_engine.extract_js_imports(src)


def test_js_require() -> None:
    src = "const cfg = require('./config');"
    assert "./config" in ts_engine.extract_js_imports(src)


def test_js_dynamic_import() -> None:
    src = "const mod = import('./lazy');"
    assert "./lazy" in ts_engine.extract_js_imports(src)


def test_js_export_from() -> None:
    src = "export { thing } from './thing';"
    assert "./thing" in ts_engine.extract_js_imports(src)


def test_js_export_star_from() -> None:
    src = "export * from './api';"
    assert "./api" in ts_engine.extract_js_imports(src)


def test_js_full_suite_matches_regex_baseline() -> None:
    src = """
import express from "express";
import { auth } from "./auth";
import "./setup";
const cfg = require("./config");
const lazy = import("./dynamic");
export { thing } from "./thing";
export * from "./api";
"""
    result = set(ts_engine.extract_js_imports(src))
    assert result == {"express", "./auth", "./setup", "./config", "./dynamic", "./thing", "./api"}


# ---------------------------------------------------------------------------
# JavaScript — tree-sitter improvements over regex
# ---------------------------------------------------------------------------


def test_js_multiline_import_not_missed() -> None:
    """Regex patterns can miss multiline imports; tree-sitter handles them."""
    src = (
        "import {\n"
        "  Component,\n"
        "  Injectable\n"
        "} from '@angular/core';\n"
    )
    assert "@angular/core" in ts_engine.extract_js_imports(src)


def test_js_no_false_positive_from_string_literal() -> None:
    """Regex can match import-like text inside string literals; tree-sitter won't."""
    src = 'const msg = "import foo from \'bar\'";\n'
    result = ts_engine.extract_js_imports(src)
    assert "bar" not in result
    assert result == []


def test_js_no_false_positive_from_comment() -> None:
    """Regex can match import statements inside comments."""
    src = "// import something from 'commented-out-dep'\n"
    result = ts_engine.extract_js_imports(src)
    assert "commented-out-dep" not in result
    assert result == []


def test_js_non_require_call_not_captured() -> None:
    """Only calls to `require()` (not `myRequire()`) should be captured."""
    src = "const x = myRequire('./should-not-match');"
    result = ts_engine.extract_js_imports(src)
    assert "./should-not-match" not in result


def test_js_deduplication() -> None:
    src = "import './a';\nimport './a';"
    assert ts_engine.extract_js_imports(src).count("./a") == 1


# ---------------------------------------------------------------------------
# TypeScript — basic coverage
# ---------------------------------------------------------------------------


def test_ts_named_import() -> None:
    src = "import { Component } from '@angular/core';"
    assert "@angular/core" in ts_engine.extract_ts_imports(src)


def test_ts_import_type() -> None:
    src = "import type { Foo } from './types';"
    assert "./types" in ts_engine.extract_ts_imports(src)


def test_ts_export_type_from() -> None:
    src = "export type { Bar } from './bar-types';"
    assert "./bar-types" in ts_engine.extract_ts_imports(src)


def test_ts_dynamic_import() -> None:
    src = "const lazy = import('./lazy-module');"
    assert "./lazy-module" in ts_engine.extract_ts_imports(src)


def test_ts_multiline_import() -> None:
    src = (
        "import {\n"
        "  A,\n"
        "  B,\n"
        "  C,\n"
        "} from './multi';\n"
    )
    assert "./multi" in ts_engine.extract_ts_imports(src)


def test_ts_no_false_positive_from_comment() -> None:
    src = "// import { x } from 'commented'\n"
    assert "commented" not in ts_engine.extract_ts_imports(src)


def test_ts_no_false_positive_from_string() -> None:
    src = 'const s = "import { x } from \'inside-string\'";\n'
    assert "inside-string" not in ts_engine.extract_ts_imports(src)


# ---------------------------------------------------------------------------
# TSX variant
# ---------------------------------------------------------------------------


def test_tsx_import_in_component_file() -> None:
    src = (
        "import React from 'react';\n"
        "import { Button } from './Button';\n"
        "export default function App() { return <Button />; }\n"
    )
    result = ts_engine.extract_ts_imports(src, tsx=True)
    assert "react" in result
    assert "./Button" in result


# ---------------------------------------------------------------------------
# Integration: JSParser and TSParser use tree-sitter when available
# ---------------------------------------------------------------------------


def test_jsparser_uses_tree_sitter_for_multiline() -> None:
    from archmap.core.parser.js_parser import JSParser

    src = (
        "import {\n"
        "  deeplyNested,\n"
        "} from './deep';\n"
    )
    result = JSParser().parse(src)
    assert "./deep" in result


def test_tsparser_uses_tree_sitter_for_multiline() -> None:
    from archmap.core.parser.ts_parser import TSParser

    src = (
        "import type {\n"
        "  MyType,\n"
        "} from './types';\n"
    )
    result = TSParser().parse(src)
    assert "./types" in result


def test_tsparser_tree_sitter_plus_triple_slash() -> None:
    """tree-sitter handles imports; triple-slash refs are still extracted via regex."""
    from archmap.core.parser.ts_parser import TSParser

    src = (
        '/// <reference path="./globals.d.ts" />\n'
        "import { x } from './x';\n"
    )
    result = TSParser().parse(src)
    assert "./globals.d.ts" in result
    assert "./x" in result
