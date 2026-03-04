import assert from "node:assert/strict";
import test from "node:test";

import { parseJsTsImports } from "../core/parser/jsTsParser.js";
import { parsePythonImports } from "../core/parser/pythonParser.js";
import { parseRustImports } from "../core/parser/rustParser.js";

test("parseJsTsImports handles import, require, export-from, and dynamic import", () => {
  const source = `
    import express from "express";
    import { auth } from "./auth";
    const cfg = require("./config");
    const lazy = import("./dynamic");
    export { thing } from "./thing";
  `;

  const imports = parseJsTsImports(source);

  assert.deepEqual(
    new Set(imports),
    new Set(["express", "./auth", "./config", "./dynamic", "./thing"])
  );
});

test("parsePythonImports handles import and from-import statements", () => {
  const source = `
import os
import app.utils as utils
from .services import auth, cache
from framework.http import Request
`;

  const imports = parsePythonImports(source);

  assert.deepEqual(imports, [
    { type: "import", module: "os" },
    { type: "import", module: "app.utils" },
    { type: "from", module: ".services", names: ["auth", "cache"] },
    { type: "from", module: "framework.http", names: ["Request"] },
  ]);
});

test("parseRustImports handles use, mod and extern crate statements", () => {
  const source = `
use crate::core::graph::builder;
use serde::{Serialize, Deserialize};
mod parser;
extern crate tokio;
`;

  const imports = parseRustImports(source);

  assert.deepEqual(imports, [
    { type: "use", path: "crate::core::graph::builder" },
    { type: "use", path: "serde" },
    { type: "mod", module: "parser" },
    { type: "extern", crate: "tokio" },
  ]);
});
