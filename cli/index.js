#!/usr/bin/env node

import path from "node:path";

import { analyzeProject } from "../core/index.js";
import { exportGraphAsJson } from "../exporters/jsonExporter.js";
import { startWebUi } from "../web-ui/server.js";

const DEFAULT_OUTPUT_PATH = ".codeatlas/graph.json";
const DEFAULT_PORT = 3000;

async function main() {
  const rawArgs = process.argv.slice(2);

  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    printHelp();
    return;
  }

  const command = rawArgs[0];

  if (command === "analyze") {
    await runAnalyze(rawArgs.slice(1));
    return;
  }

  if (command === "serve") {
    await runServe(rawArgs.slice(1));
    return;
  }

  if (command === "version" || command === "--version" || command === "-v") {
    console.log("code-arch 0.1.0");
    return;
  }

  await runServe(rawArgs);
}

async function runAnalyze(args) {
  const options = parseArgs(args);
  const target = options._[0] ?? ".";
  const outputPath = options.out ?? DEFAULT_OUTPUT_PATH;

  const report = await analyzeProject(target);
  const absoluteOutputPath = await exportGraphAsJson(report, outputPath);

  printSummary(report);
  printTopFiles(report);
  console.log(`ℹ JSON exportado em ${absoluteOutputPath}`);
}

async function runServe(args) {
  const options = parseArgs(args);
  const target = options._[0] ?? ".";
  const outputPath = options.out ?? DEFAULT_OUTPUT_PATH;
  const port = toPort(options.port, DEFAULT_PORT);
  const openBrowser = !options["no-open"];

  const report = await analyzeProject(target);
  const absoluteOutputPath = await exportGraphAsJson(report, outputPath);

  printSummary(report);
  printTopFiles(report);

  const { url } = await startWebUi({ report, port, openBrowser });
  console.log(`ℹ Relatório salvo em ${absoluteOutputPath}`);
  console.log(`ℹ Visualização disponível em ${url}`);
  console.log("ℹ Pressione Ctrl+C para encerrar.");
}

function printSummary(report) {
  const { filesAnalyzed, totalDependencies, circularDependencyCount } = report.metrics;

  console.log(`✔ ${filesAnalyzed} arquivos analisados`);
  console.log(`✔ ${totalDependencies} dependências detectadas`);

  if (circularDependencyCount > 0) {
    console.log(`⚠ ${circularDependencyCount} circular dependencies encontradas`);
  } else {
    console.log("✔ 0 circular dependencies encontradas");
  }
}

function printTopFiles(report) {
  const topComplexity = report.metrics.complexity.slice(0, 5);
  const topCritical = report.metrics.criticalFiles.slice(0, 5);

  if (topComplexity.length > 0) {
    console.log("Complexidade (top 5):");
    for (const entry of topComplexity) {
      console.log(`  - ${entry.file}: ${entry.imports} imports`);
    }
  }

  if (topCritical.length > 0) {
    console.log("Arquivos críticos (top 5):");
    for (const entry of topCritical) {
      console.log(`  - ${entry.file}: ${entry.dependents} dependentes`);
    }
  }
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

function printHelp() {
  console.log("CodeAtlas - Visualize architecture dependencies");
  console.log("");
  console.log("Uso:");
  console.log("  code-arch analyze <path> [--out <file>]");
  console.log("  code-arch serve <path> [--port 3000] [--no-open] [--out <file>]");
  console.log("  code-arch <path> [--port 3000]");
  console.log("");
  console.log("Exemplos:");
  console.log(`  code-arch analyze ./project --out ${path.normalize(DEFAULT_OUTPUT_PATH)}`);
  console.log("  code-arch .");
}

main().catch((error) => {
  console.error("Erro durante a execução:", error.message);
  process.exit(1);
});
