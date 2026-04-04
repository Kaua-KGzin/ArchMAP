from __future__ import annotations

from archmap.core.parser.js_parser import JSParser
from archmap.core.parser.python_parser import PythonParser
from archmap.core.parser.rust_parser import RustParser
from archmap.core.parser.ts_parser import TSParser


def test_parse_js_imports_supports_import_export_require_and_dynamic_import() -> None:
    source = """
import express from "express";
import { auth } from "./auth";
import "./setup";
const cfg = require("./config");
const lazy = import("./dynamic");
export { thing } from "./thing";
export * from "./api";
"""
    parser = JSParser()
    imports = parser.parse(source)
    assert set(imports) == {
        "express",
        "./auth",
        "./setup",
        "./config",
        "./dynamic",
        "./thing",
        "./api",
    }


def test_parse_js_imports_ignores_comments_strings_and_templates() -> None:
    source = """
// import fake from "fake";
/* export { nope } from "./hidden"; */
const text = "require('./not-real')";
const tpl = `import hidden from "./template"`;
const prop = loader.require("./not-counted");
import real from "./real";
const cfg = require("./config");
"""
    parser = JSParser()
    imports = parser.parse(source)
    assert set(imports) == {"./real", "./config"}


def test_js_parser_ignores_regex_with_import_keyword() -> None:
    source = """
const validator = /import "react"/;
const dependency = require("./real");
"""
    parser = JSParser()
    imports = parser.parse(source)
    assert imports == ["./real"]


def test_js_parser_supports_static_template_literals_in_dynamic_imports() -> None:
    source = """
const lazy = import(`./utils`);
const cfg = require(`./config`);
const dynamic = import(`./modules/${name}`);
"""
    parser = JSParser()
    imports = parser.parse(source)
    assert set(imports) == {"./utils", "./config"}


def test_js_parser_handles_many_block_comments_before_import() -> None:
    source = ("/* many comments */\n" * 200) + 'import service from "./service";\n'
    parser = JSParser()
    imports = parser.parse(source)
    assert imports == ["./service"]


def test_parse_ts_imports_supports_type_only_syntax() -> None:
    source = """
import type { User } from "./types";
export type { UserDto } from "./dto";
"""
    parser = TSParser()
    imports = parser.parse(source)
    assert set(imports) == {"./types", "./dto"}


def test_parse_python_imports_supports_import_and_from_import() -> None:
    source = """
import os
import app.utils as utils
from .services import auth, cache
from framework.http import Request
"""
    parser = PythonParser()
    imports = parser.parse(source)
    assert imports == [
        {"type": "import", "module": "os", "names": []},
        {"type": "import", "module": "app.utils", "names": []},
        {"type": "from", "module": ".services", "names": ["auth", "cache"]},
        {"type": "from", "module": "framework.http", "names": ["Request"]},
    ]


def test_parse_python_imports_supports_multiline_forms() -> None:
    source = """
import os, \\
    sys
from pkg import (
    service,
    cache,
)
"""
    parser = PythonParser()
    imports = parser.parse(source)
    assert imports == [
        {"type": "import", "module": "os", "names": []},
        {"type": "import", "module": "sys", "names": []},
        {"type": "from", "module": "pkg", "names": ["service", "cache"]},
    ]


def test_parse_python_imports_falls_back_to_regex_for_invalid_files() -> None:
    source = """
import os
if True print("broken")
"""
    parser = PythonParser()
    imports = parser.parse(source)
    assert imports == [{"type": "import", "module": "os", "names": []}]


def test_parse_rust_imports_supports_use_mod_and_extern() -> None:
    source = """
use crate::core::graph::builder;
use serde::{Serialize, Deserialize};
mod parser;
extern crate tokio;
"""
    parser = RustParser()
    imports = parser.parse(source)
    assert imports == [
        {"type": "use", "path": "crate::core::graph::builder", "module": "", "crate": ""},
        {"type": "use", "path": "serde", "module": "", "crate": ""},
        {"type": "mod", "path": "", "module": "parser", "crate": ""},
        {"type": "extern", "path": "", "module": "", "crate": "tokio"},
    ]


def test_js_parser_resolve():
    parser = JSParser()
    imports = ["express", "./auth"]
    file_ids = {"src/main.js", "src/auth.js"}
    deps = parser.resolve(imports, "src/main.js", file_ids)
    assert len(deps) == 2
    assert {"id": "pkg:express", "label": "express", "type": "package"} in deps
    assert {"id": "src/auth.js", "label": "src/auth.js", "type": "file"} in deps


def test_ts_parser_methods():
    parser = TSParser()
    assert parser.language == "typescript"
    source = "import React from 'react';"
    imports = parser.parse(source)
    assert imports == ["react"]
    deps = parser.resolve(imports, "src/Component.tsx", {"src/Component.tsx"})
    assert deps == [{"id": "pkg:react", "label": "react", "type": "package"}]
