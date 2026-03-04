import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { exportGraphAsJson } from "../exporters/jsonExporter.js";
import { exportGraphAsMermaid } from "../exporters/mermaidExporter.js";

test("exporters create JSON and Mermaid files", async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "archmap-export-"));
  const jsonPath = path.join(tempRoot, "graph.json");
  const mermaidPath = path.join(tempRoot, "graph.mmd");

  const report = {
    projectRoot: "/repo",
    nodes: [
      {
        id: "src/server.js",
        label: "src/server.js",
        type: "file",
        outgoing: 1,
        incoming: 0,
        complexityImports: 1,
        complexityScore: 1,
      },
      {
        id: "pkg:express",
        label: "express",
        type: "package",
        outgoing: 0,
        incoming: 1,
        complexityImports: 0,
        complexityScore: 0,
      },
    ],
    edges: [{ id: "src/server.js->pkg:express", source: "src/server.js", target: "pkg:express" }],
    metrics: {
      filesAnalyzed: 1,
      totalDependencies: 1,
      externalDependencies: 1,
      circularDependencyCount: 0,
      complexity: [{ file: "src/server.js", imports: 1, score: 1 }],
      criticalFiles: [{ file: "src/server.js", dependents: 0 }],
    },
    cycles: [],
    simple: {
      nodes: ["src/server.js", "pkg:express"],
      edges: [["src/server.js", "pkg:express"]],
    },
  };

  await exportGraphAsJson(report, jsonPath);
  await exportGraphAsMermaid(report, mermaidPath);

  const jsonContent = await fs.readFile(jsonPath, "utf8");
  const mermaidContent = await fs.readFile(mermaidPath, "utf8");

  assert.match(jsonContent, /"nodes"/);
  assert.match(mermaidContent, /^graph TD/m);
  assert.match(mermaidContent, /pkg_express/);
  assert.match(mermaidContent, /file_src_server_js --> pkg_express/);
});
