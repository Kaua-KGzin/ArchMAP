import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const projectRoot = process.cwd();
const cliPath = path.join(projectRoot, "cli", "index.js");

test("CLI analyze with --format both exports JSON and Mermaid", async () => {
  const fixtureRoot = await fs.mkdtemp(path.join(os.tmpdir(), "archmap-cli-"));
  const jsonPath = path.join(fixtureRoot, "out.json");
  const mermaidPath = path.join(fixtureRoot, "out.mmd");

  await fs.writeFile(
    path.join(fixtureRoot, "server.js"),
    'import express from "express";\nimport { auth } from "./auth.js";\n',
    "utf8"
  );
  await fs.writeFile(path.join(fixtureRoot, "auth.js"), 'export const auth = true;\n', "utf8");

  const run = spawnSync(
    process.execPath,
    [
      cliPath,
      "analyze",
      fixtureRoot,
      "--format",
      "both",
      "--out",
      jsonPath,
      "--out-mermaid",
      mermaidPath,
    ],
    { cwd: projectRoot, encoding: "utf8" }
  );

  assert.equal(run.status, 0, run.stderr || run.stdout);

  const jsonExists = await fileExists(jsonPath);
  const mermaidExists = await fileExists(mermaidPath);

  assert.equal(jsonExists, true);
  assert.equal(mermaidExists, true);
});

test("CLI analyze with --format mermaid exports only Mermaid output", async () => {
  const fixtureRoot = await fs.mkdtemp(path.join(os.tmpdir(), "archmap-cli-"));
  const jsonPath = path.join(fixtureRoot, "out.json");
  const mermaidPath = path.join(fixtureRoot, "out.mmd");

  await fs.writeFile(path.join(fixtureRoot, "entry.js"), 'import "./module.js";\n', "utf8");
  await fs.writeFile(path.join(fixtureRoot, "module.js"), "export {};\n", "utf8");

  const run = spawnSync(
    process.execPath,
    [
      cliPath,
      "analyze",
      fixtureRoot,
      "--format",
      "mermaid",
      "--out",
      jsonPath,
      "--out-mermaid",
      mermaidPath,
    ],
    { cwd: projectRoot, encoding: "utf8" }
  );

  assert.equal(run.status, 0, run.stderr || run.stdout);
  assert.equal(await fileExists(mermaidPath), true);
  assert.equal(await fileExists(jsonPath), false);
});

async function fileExists(filePath) {
  try {
    await fs.stat(filePath);
    return true;
  } catch (error) {
    return false;
  }
}
