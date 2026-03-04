import assert from "node:assert/strict";
import test from "node:test";

import { analyzeGraph } from "../core/analyzer/index.js";
import { buildGraph } from "../core/graph/index.js";

test("analyzer computes cycles, critical files and normalized complexity", () => {
  const parsedProject = {
    projectRoot: "/workspace",
    parsedFiles: [
      {
        id: "a.js",
        label: "a.js",
        language: "javascript",
        dependencies: [
          { id: "b.js", label: "b.js", type: "file" },
          { id: "pkg:express", label: "express", type: "package" },
        ],
      },
      {
        id: "b.js",
        label: "b.js",
        language: "javascript",
        dependencies: [{ id: "a.js", label: "a.js", type: "file" }],
      },
      {
        id: "c.js",
        label: "c.js",
        language: "javascript",
        dependencies: [{ id: "a.js", label: "a.js", type: "file" }],
      },
    ],
  };

  const graph = buildGraph(parsedProject);
  const report = analyzeGraph(graph);

  assert.equal(report.metrics.filesAnalyzed, 3);
  assert.equal(report.metrics.circularDependencyCount, 1);
  assert.equal(report.cycles.length, 1);
  assert.deepEqual(report.cycles[0], ["a.js", "b.js"]);

  const aNode = report.nodes.find((node) => node.id === "a.js");
  const bNode = report.nodes.find((node) => node.id === "b.js");
  const cNode = report.nodes.find((node) => node.id === "c.js");

  assert.equal(aNode.complexityImports, 2);
  assert.equal(aNode.complexityScore, 1);
  assert.equal(bNode.complexityImports, 1);
  assert.equal(cNode.complexityImports, 1);
  assert.equal(cNode.complexityScore, 0.5);

  const mostCritical = report.metrics.criticalFiles[0];
  assert.equal(mostCritical.file, "a.js");
  assert.equal(mostCritical.dependents, 2);
});
