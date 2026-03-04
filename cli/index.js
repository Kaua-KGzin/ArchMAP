#!/usr/bin/env node

import path from "node:path";

import { analyzeProject } from "../core/index.js";
import { exportGraphAsJson } from "../exporters/jsonExporter.js";
import { exportGraphAsMermaid } from "../exporters/mermaidExporter.js";
import { startWebUi } from "../web-ui/server.js";

const DEFAULT_JSON_OUTPUT_PATH = ".codeatlas/graph.json";
const DEFAULT_MERMAID_OUTPUT_PATH = ".codeatlas/graph.mmd";
const DEFAULT_PORT = 3000;
const VERSION = "0.1.0-beta.0";

async function main() {
  const rawArgs = process.argv.slice(2);

  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    printHelp();
    return;
  }

  const command = rawArgs[0];
  const executable = path.basename(process.argv[1] ?? "archmap");
  const isVersionRequest =
    command === "version" || command === "--version" || command === "-v";

  if (isVersionRequest) {
    console.log(`${toolDisplayName(executable)} ${VERSION}`);
    return;
  }

  if (command === "analyze") {
    await runAnalyze(rawArgs.slice(1), executable);
    return;
  }

  if (command === "serve") {
    await runServe(rawArgs.slice(1), executable);
    return;
  }

  await runServe(rawArgs, executable);
}

async function runAnalyze(args, executable) {
  const options = parseArgs(args);
  const target = options._[0] ?? ".";
  const format = parseFormatOption(options.format, "json");
  const outputPath = options.out ?? DEFAULT_JSON_OUTPUT_PATH;
  const mermaidOutputPath = options["out-mermaid"] ?? DEFAULT_MERMAID_OUTPUT_PATH;

  const report = await analyzeProject(target);
  const exportResult = await exportOutputs(report, { format, outputPath, mermaidOutputPath });

  printSummary(report);
  printTopFiles(report);
  printExportSummary(exportResult);
  printCommandHint(executable, target);
}

async function runServe(args, executable) {
  const options = parseArgs(args);
  const target = options._[0] ?? ".";
  const format = parseFormatOption(options.format, "both");
  const outputPath = options.out ?? DEFAULT_JSON_OUTPUT_PATH;
  const mermaidOutputPath = options["out-mermaid"] ?? DEFAULT_MERMAID_OUTPUT_PATH;
  const port = toPort(options.port, DEFAULT_PORT);
  const openBrowser = !options["no-open"];

  const report = await analyzeProject(target);
  const exportResult = await exportOutputs(report, { format, outputPath, mermaidOutputPath });

  printSummary(report);
  printTopFiles(report);
  printExportSummary(exportResult);

  const { url } = await startWebUi({ report, port, openBrowser });
  console.log(`[info] Web UI available at ${url}`);
  console.log("[info] Press Ctrl+C to stop.");
}

async function exportOutputs(report, { format, outputPath, mermaidOutputPath }) {
  const result = {
    jsonPath: null,
    mermaidPath: null,
  };

  if (format === "json" || format === "both") {
    result.jsonPath = await exportGraphAsJson(report, outputPath);
  }

  if (format === "mermaid" || format === "both") {
    result.mermaidPath = await exportGraphAsMermaid(report, mermaidOutputPath);
  }

  return result;
}

function printSummary(report) {
  const { filesAnalyzed, totalDependencies, circularDependencyCount } = report.metrics;

  console.log(`[ok] ${filesAnalyzed} files analyzed`);
  console.log(`[ok] ${totalDependencies} dependencies detected`);
  console.log(`[ok] ${circularDependencyCount} circular dependencies detected`);
}

function printTopFiles(report) {
  const topComplexity = report.metrics.complexity.slice(0, 5);
  const topCritical = report.metrics.criticalFiles.slice(0, 5);

  if (topComplexity.length > 0) {
    console.log("Top complexity (imports):");
    for (const entry of topComplexity) {
      const percentage = Math.round(entry.score * 100);
      console.log(`  - ${entry.file}: ${entry.imports} imports (${percentage}% score)`);
    }
  }

  if (topCritical.length > 0) {
    console.log("Top critical files (dependents):");
    for (const entry of topCritical) {
      console.log(`  - ${entry.file}: ${entry.dependents} dependents`);
    }
  }
}

function printExportSummary(exportResult) {
  if (exportResult.jsonPath) {
    console.log(`[info] JSON report exported to ${exportResult.jsonPath}`);
  }
  if (exportResult.mermaidPath) {
    console.log(`[info] Mermaid graph exported to ${exportResult.mermaidPath}`);
  }
}

function printCommandHint(executable, target) {
  console.log(
    `[hint] Run "${toolDisplayName(executable)} serve ${target}" to open the interactive graph.`
  );
}

function parseArgs(args) {
  const parsed = { _: [] };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (!arg.startsWith("--")) {
      parsed._.push(arg);
      continue;
    }

    const [rawKey, inlineValue] = arg.split("=");
    const key = rawKey.replace(/^--/, "");

    if (inlineValue !== undefined) {
      parsed[key] = inlineValue;
      continue;
    }

    const maybeValue = args[index + 1];
    if (maybeValue && !maybeValue.startsWith("--")) {
      parsed[key] = maybeValue;
      index += 1;
      continue;
    }

    parsed[key] = true;
  }

  return parsed;
}

function parseFormatOption(rawFormat, fallbackFormat) {
  const normalized = String(rawFormat ?? fallbackFormat).toLowerCase();
  const allowed = new Set(["json", "mermaid", "both"]);
  if (!allowed.has(normalized)) {
    throw new Error(`Invalid --format value "${rawFormat}". Allowed: json, mermaid, both.`);
  }
  return normalized;
}

function toPort(value, fallbackPort) {
  if (value === undefined) {
    return fallbackPort;
  }

  const parsedPort = Number(value);
  if (Number.isInteger(parsedPort) && parsedPort > 0 && parsedPort < 65536) {
    return parsedPort;
  }
  return fallbackPort;
}

function toolDisplayName(executable) {
  if (executable.toLowerCase().includes("code-arch")) {
    return "code-arch";
  }
  return "archmap";
}

function printHelp() {
  const defaultTool = "archmap";
  const aliasTool = "code-arch";

  console.log("ArchMAP - Visualize architecture dependencies");
  console.log("");
  console.log("Usage:");
  console.log(
    `  ${defaultTool} analyze <path> [--format json|mermaid|both] [--out <file>] [--out-mermaid <file>]`
  );
  console.log(
    `  ${defaultTool} serve <path> [--format json|mermaid|both] [--port 3000] [--no-open] [--out <file>] [--out-mermaid <file>]`
  );
  console.log(`  ${defaultTool} <path> [--format json|mermaid|both] [--port 3000]`);
  console.log("");
  console.log(`Alias: ${aliasTool}`);
  console.log("");
  console.log("Examples:");
  console.log(
    `  ${defaultTool} analyze ./project --format both --out ${path.normalize(DEFAULT_JSON_OUTPUT_PATH)} --out-mermaid ${path.normalize(DEFAULT_MERMAID_OUTPUT_PATH)}`
  );
  console.log(`  ${defaultTool} serve ./project --port 3000`);
}

main().catch((error) => {
  console.error("[error] Execution failed:", error.message);
  process.exit(1);
});
