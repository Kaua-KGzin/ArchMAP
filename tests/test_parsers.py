from __future__ import annotations

from archmap.core.parser.js_parser import parse_js_imports
from archmap.core.parser.python_parser import parse_python_imports
from archmap.core.parser.rust_parser import parse_rust_imports


def test_parse_js_imports_supports_import_export_require_and_dynamic_import() -> None:
    source = """
import express from "express";
import { auth } from "./auth";
const cfg = require("./config");
const lazy = import("./dynamic");
export { thing } from "./thing";
"""
    imports = parse_js_imports(source)
    assert set(imports) == {"express", "./auth", "./config", "./dynamic", "./thing"}


def test_parse_python_imports_supports_import_and_from_import() -> None:
    source = """
import os
import app.utils as utils
from .services import auth, cache
from framework.http import Request
"""
    imports = parse_python_imports(source)
    assert imports == [
        {"type": "import", "module": "os", "names": []},
        {"type": "import", "module": "app.utils", "names": []},
        {"type": "from", "module": ".services", "names": ["auth", "cache"]},
        {"type": "from", "module": "framework.http", "names": ["Request"]},
    ]


def test_parse_rust_imports_supports_use_mod_and_extern() -> None:
    source = """
use crate::core::graph::builder;
use serde::{Serialize, Deserialize};
mod parser;
extern crate tokio;
"""
    imports = parse_rust_imports(source)
    assert imports == [
        {"type": "use", "path": "crate::core::graph::builder", "module": "", "crate": ""},
        {"type": "use", "path": "serde", "module": "", "crate": ""},
        {"type": "mod", "path": "", "module": "parser", "crate": ""},
        {"type": "extern", "path": "", "module": "", "crate": "tokio"},
    ]
