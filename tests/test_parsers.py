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
    assert set(imports) == {"express", "./auth", "./setup", "./config", "./dynamic", "./thing", "./api"}


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
