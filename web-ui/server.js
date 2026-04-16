import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import express from "express";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const staticDirectory = path.join(__dirname, "..", "src", "archmap", "web-ui", "static");

const DEFAULT_HOST = "0.0.0.0";
const DEFAULT_PORT = 3000;
const DEFAULT_SEARCH_LIMIT = 30;

export async function startWebUi(options = {}) {
  const {
    report = null,
    reportProvider = null,
    projectPath = ".",
    host = DEFAULT_HOST,
    port = DEFAULT_PORT,
    openBrowser = true,
    staticDir = staticDirectory,
  } = options;

  const provider = reportProvider ?? createInMemoryReportStore({ report, projectPath });
  await provider.ensureLoaded();

  const app = express();
  app.use(express.json({ limit: "256kb" }));

  app.get("/api/graph", async (_request, response) => {
    const currentReport = await provider.getReport();
    response.json(currentReport);
  });

  app.get("/api/project", (_request, response) => {
    response.json({
      path: provider.getProjectPath(),
      updatedAt: provider.getUpdatedAt(),
    });
  });

  app.get("/api/history", (_request, response) => {
    response.status(501).json({
      status: "unsupported",
      message: "Architecture history is available through `archmap serve`.",
    });
  });

  app.get("/api/metrics", async (_request, response) => {
    const currentReport = await provider.getReport();
    response.json({
      metrics: currentReport.metrics ?? {},
      riskSummary: summarizeRiskCounts(currentReport),
    });
  });

  app.get("/api/search", async (request, response) => {
    const query = String(request.query.q ?? "").trim();
    const limit = clampLimit(request.query.limit);
    const currentReport = await provider.getReport();
    response.json(searchInReport(currentReport, query, limit));
  });

  app.get("/api/node/:id", async (request, response) => {
    const nodeId = decodeURIComponent(request.params.id);
    const currentReport = await provider.getReport();
    const nodeData = inspectNode(currentReport, nodeId);
    if (!nodeData) {
      response.status(404).json({ error: "Node not found", id: nodeId });
      return;
    }
    response.json(nodeData);
  });

  app.post("/api/reanalyze", async (_request, response) => {
    try {
      await provider.reanalyze();
      response.json({
        status: "success",
        path: provider.getProjectPath(),
        updatedAt: provider.getUpdatedAt(),
      });
    } catch (error) {
      response.status(500).json({
        status: "error",
        message: formatError(error),
      });
    }
  });

  app.post("/api/open", (_request, response) => {
    response.status(501).json({
      status: "unsupported",
      mode: "manual_path",
      message: "Directory picker is unavailable in the Node development server.",
    });
  });

  app.post("/api/open-file", async (request, response) => {
    const nodeId = String(request.body?.nodeId ?? "").trim();
    if (!nodeId) {
      response.status(400).json({ status: "error", message: "body.nodeId is required" });
      return;
    }

    const currentReport = await provider.getReport();
    const targetPath = await resolveNodeFilePath(provider.getProjectPath(), currentReport, nodeId);
    if (!targetPath) {
      response.status(404).json({
        status: "error",
        message: `File node not found or unavailable: ${nodeId}`,
      });
      return;
    }

    try {
      tryOpenPath(targetPath);
    } catch (error) {
      response.status(500).json({
        status: "error",
        message: formatError(error),
      });
      return;
    }

    response.json({
      status: "success",
      path: targetPath,
    });
  });

  app.post("/api/project", async (request, response) => {
    const nextPath = String(request.body?.path ?? "").trim();
    if (!nextPath) {
      response.status(400).json({ status: "error", message: "body.path is required" });
      return;
    }
    try {
      await provider.setProjectPath(nextPath);
      response.json({
        status: "success",
        path: provider.getProjectPath(),
        updatedAt: provider.getUpdatedAt(),
      });
    } catch (error) {
      response.status(500).json({
        status: "error",
        message: formatError(error),
      });
    }
  });

  app.get("/api/health", (_request, response) => {
    response.json({
      status: "ok",
      path: provider.getProjectPath(),
      updatedAt: provider.getUpdatedAt(),
    });
  });

  app.use(express.static(staticDir));
  app.get(/.*/, (_request, response) => {
    response.sendFile(path.join(staticDir, "index.html"));
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(port, host, () => {
      const browserHost = browserHostFor(host);
      const url = `http://${browserHost}:${port}`;
      if (openBrowser) {
        tryOpenBrowser(url);
      }
      resolve({
        server,
        url,
        close: () => closeServer(server),
        reportProvider: provider,
      });
    });

    server.on("error", reject);
  });
}

export function createInMemoryReportStore({ report = null, projectPath = "." } = {}) {
  let currentReport = report ?? {
    projectRoot: projectPath,
    nodes: [],
    edges: [],
    metrics: {},
    cycles: [],
    risks: {},
  };
  let currentPath = projectPath;
  let updatedAt = new Date().toISOString();

  return {
    async ensureLoaded() {
      if (!currentReport) {
        currentReport = {
          projectRoot: currentPath,
          nodes: [],
          edges: [],
          metrics: {},
          cycles: [],
          risks: {},
        };
      }
    },
    async getReport() {
      return currentReport;
    },
    async setReport(nextReport) {
      currentReport = nextReport ?? currentReport;
      updatedAt = new Date().toISOString();
    },
    async setProjectPath(nextPath) {
      currentPath = nextPath;
      await this.reanalyze();
    },
    async reanalyze() {
      updatedAt = new Date().toISOString();
    },
    getProjectPath() {
      return currentPath;
    },
    getUpdatedAt() {
      return updatedAt;
    },
  };
}

export function createPythonReportProvider({
  projectPath = ".",
  pythonCmd = "python",
  extraArgs = [],
} = {}) {
  let currentPath = projectPath;
  let currentReport = null;
  let updatedAt = null;

  async function analyzeWithPython() {
    const tempFile = path.join(
      os.tmpdir(),
      `archmap-report-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}.json`
    );
    const args = [
      "-m",
      "archmap.cli.main",
      "analyze",
      currentPath,
      "--format",
      "json",
      "--out",
      tempFile,
      ...extraArgs,
    ];

    await runProcess(pythonCmd, args);
    try {
      const text = await fs.readFile(tempFile, "utf-8");
      currentReport = JSON.parse(text);
      updatedAt = new Date().toISOString();
    } finally {
      await fs.unlink(tempFile).catch(() => undefined);
    }
  }

  return {
    async ensureLoaded() {
      if (!currentReport) {
        await analyzeWithPython();
      }
    },
    async getReport() {
      await this.ensureLoaded();
      return currentReport;
    },
    async reanalyze() {
      await analyzeWithPython();
    },
    async setProjectPath(nextPath) {
      currentPath = nextPath;
      await analyzeWithPython();
    },
    getProjectPath() {
      return currentPath;
    },
    getUpdatedAt() {
      return updatedAt;
    },
  };
}

function clampLimit(rawLimit) {
  const parsed = Number.parseInt(String(rawLimit ?? DEFAULT_SEARCH_LIMIT), 10);
  if (!Number.isFinite(parsed)) {
    return DEFAULT_SEARCH_LIMIT;
  }
  return Math.max(1, Math.min(200, parsed));
}

function searchInReport(report, query, limit) {
  const nodes = Array.isArray(report?.nodes) ? report.nodes : [];
  const normalizedQuery = query.toLowerCase();
  const filtered = normalizedQuery
    ? nodes.filter((node) => {
        const id = String(node?.id ?? "").toLowerCase();
        const label = String(node?.label ?? "").toLowerCase();
        return id.includes(normalizedQuery) || label.includes(normalizedQuery);
      })
    : nodes;

  const results = filtered.slice(0, limit).map((node) => ({
    id: node.id,
    label: node.label,
    type: node.type,
    folder: node.folder,
    language: node.language,
  }));

  return {
    query,
    limit,
    total: filtered.length,
    results,
  };
}

function inspectNode(report, nodeId) {
  const nodes = Array.isArray(report?.nodes) ? report.nodes : [];
  const edges = Array.isArray(report?.edges) ? report.edges : [];
  const node = nodes.find((candidate) => candidate?.id === nodeId);
  if (!node) {
    return null;
  }

  const incoming = edges.filter((edge) => edge.target === nodeId);
  const outgoing = edges.filter((edge) => edge.source === nodeId);

  return {
    node,
    incoming,
    outgoing,
  };
}

async function resolveNodeFilePath(projectPath, report, nodeId) {
  const nodes = Array.isArray(report?.nodes) ? report.nodes : [];
  const node = nodes.find((candidate) => candidate?.id === nodeId);
  if (!node || node.type !== "file") {
    return null;
  }

  const normalizedNodeId = String(nodeId).replaceAll("\\", "/");
  const projectRoot = path.resolve(String(report?.projectRoot ?? projectPath ?? "."));
  return candidateFilePath(projectRoot, normalizedNodeId);
}

async function candidateFilePath(projectRoot, normalizedNodeId) {
  const relativePath = normalizedNodeId.split("/").join(path.sep);
  try {
    const rootStats = await fs.stat(projectRoot);
    if (rootStats.isFile()) {
      if (path.basename(projectRoot).replaceAll("\\", "/") === normalizedNodeId) {
        return projectRoot;
      }
      const candidate = path.resolve(path.dirname(projectRoot), relativePath);
      try {
        const candidateStats = await fs.stat(candidate);
        return candidateStats.isFile() ? candidate : null;
      } catch {
        return null;
      }
    }

    const candidate = path.resolve(projectRoot, relativePath);
    const relativeToRoot = path.relative(projectRoot, candidate);
    if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) {
      return null;
    }

    try {
      const candidateStats = await fs.stat(candidate);
      return candidateStats.isFile() ? candidate : null;
    } catch {
      return null;
    }
  } catch {
    return null;
  }
}

function summarizeRiskCounts(report) {
  const risks = report?.risks ?? {};
  return {
    cycles: Array.isArray(report?.cycles) ? report.cycles.length : 0,
    godModules: Array.isArray(risks.god_modules) ? risks.god_modules.length : 0,
    layerViolations: Array.isArray(risks.layer_violations) ? risks.layer_violations.length : 0,
    dependencyExplosions: Array.isArray(risks.dependency_explosions)
      ? risks.dependency_explosions.length
      : 0,
  };
}

function browserHostFor(host) {
  if (host === "0.0.0.0" || host === "::") {
    return "localhost";
  }
  return host;
}

async function closeServer(server) {
  await new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

function runProcess(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "pipe",
      windowsHide: true,
    });
    const stderrChunks = [];

    child.stderr?.on("data", (chunk) => {
      stderrChunks.push(chunk);
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      const stderr = Buffer.concat(stderrChunks).toString().trim();
      reject(new Error(stderr || `${command} exited with code ${code}`));
    });
  });
}

function tryOpenBrowser(url) {
  try {
    const platform = process.platform;
    if (platform === "win32") {
      spawn("cmd", ["/c", "start", "", url], {
        detached: true,
        stdio: "ignore",
      }).unref();
      return;
    }
    if (platform === "darwin") {
      spawn("open", [url], { detached: true, stdio: "ignore" }).unref();
      return;
    }
    spawn("xdg-open", [url], { detached: true, stdio: "ignore" }).unref();
  } catch (_error) {
    // Browser opening is best-effort only.
  }
}

function tryOpenPath(targetPath) {
  const platform = process.platform;
  if (platform === "win32") {
    spawn("cmd", ["/c", "start", "", targetPath], {
      detached: true,
      stdio: "ignore",
    }).unref();
    return;
  }
  if (platform === "darwin") {
    spawn("open", [targetPath], { detached: true, stdio: "ignore" }).unref();
    return;
  }
  spawn("xdg-open", [targetPath], { detached: true, stdio: "ignore" }).unref();
}

function formatError(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
