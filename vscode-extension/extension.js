// @ts-check
"use strict";

const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const DIAGNOSTIC_SOURCE = "ArchMAP";
const JSON_OUTPUT = path.join(".codeatlas", "graph.json");

/** @type {vscode.DiagnosticCollection} */
let diagnostics;

/** @type {vscode.StatusBarItem} */
let statusBar;

/** @type {vscode.Disposable | undefined} */
let saveListener;

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_SOURCE);
  context.subscriptions.push(diagnostics);

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusBar.command = "archmap.analyze";
  statusBar.text = "$(graph) ArchMAP";
  statusBar.tooltip = "Click to run ArchMAP analysis";
  statusBar.show();
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    vscode.commands.registerCommand("archmap.analyze", () => runAnalysis(context)),
    vscode.commands.registerCommand("archmap.openUI", () => openUI(context)),
    vscode.commands.registerCommand("archmap.trace", () => traceFile(context))
  );

  const config = vscode.workspace.getConfiguration("archmap");
  if (config.get("analyzeOnSave")) {
    saveListener = vscode.workspace.onDidSaveTextDocument(() => runAnalysis(context));
    context.subscriptions.push(saveListener);
  }

  vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration("archmap.analyzeOnSave")) {
      const enabled = vscode.workspace.getConfiguration("archmap").get("analyzeOnSave");
      if (enabled && !saveListener) {
        saveListener = vscode.workspace.onDidSaveTextDocument(() => runAnalysis(context));
        context.subscriptions.push(saveListener);
      }
    }
  });
}

function deactivate() {
  diagnostics?.clear();
  statusBar?.dispose();
}

/**
 * @param {vscode.ExtensionContext} _context
 */
async function runAnalysis(_context) {
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showWarningMessage("ArchMAP: No workspace folder open.");
    return;
  }

  const exe = getExePath();
  statusBar.text = "$(sync~spin) ArchMAP: analyzing...";

  const jsonOut = path.join(root, JSON_OUTPUT);

  return new Promise((resolve) => {
    cp.execFile(
      exe,
      ["analyze", root, "--format", "json", "--quiet", "--out", jsonOut],
      { cwd: root },
      (err, _stdout, stderr) => {
        if (err && err.code !== 2) {
          statusBar.text = "$(graph) ArchMAP: error";
          vscode.window.showErrorMessage(`ArchMAP: ${stderr || err.message}`);
          resolve(undefined);
          return;
        }

        try {
          const report = JSON.parse(fs.readFileSync(jsonOut, "utf-8"));
          applyDiagnostics(report, root);
          updateStatusBar(report);
        } catch (parseErr) {
          statusBar.text = "$(graph) ArchMAP";
        }
        resolve(undefined);
      }
    );
  });
}

/**
 * @param {vscode.ExtensionContext} _context
 */
async function openUI(_context) {
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showWarningMessage("ArchMAP: No workspace folder open.");
    return;
  }

  const exe = getExePath();
  const config = vscode.workspace.getConfiguration("archmap");
  const port = /** @type {number} */ (config.get("port") ?? 3000);

  cp.spawn(exe, ["serve", root, "--port", String(port), "--no-open"], {
    cwd: root,
    detached: true,
    stdio: "ignore",
  }).unref();

  setTimeout(() => {
    vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
  }, 1500);
}

/**
 * @param {vscode.ExtensionContext} _context
 */
async function traceFile(_context) {
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showWarningMessage("ArchMAP: No workspace folder open.");
    return;
  }

  const editor = vscode.window.activeTextEditor;
  const defaultEntry = editor
    ? path.relative(root, editor.document.fileName).replace(/\\/g, "/")
    : "";

  const entry = await vscode.window.showInputBox({
    prompt: "Entrypoint file to trace (relative path)",
    value: defaultEntry,
    placeHolder: "src/main.py",
  });

  if (!entry) return;

  const exe = getExePath();
  const jsonOut = path.join(os.tmpdir(), `archmap-trace-${Date.now()}.json`);

  cp.execFile(
    exe,
    ["trace", entry, root, "--json", "--out", jsonOut],
    { cwd: root },
    (err, _stdout, stderr) => {
      if (err) {
        vscode.window.showErrorMessage(`ArchMAP trace: ${stderr || err.message}`);
        return;
      }
      try {
        const result = JSON.parse(fs.readFileSync(jsonOut, "utf-8"));
        const panel = vscode.window.createWebviewPanel(
          "archmapTrace",
          `Trace: ${entry}`,
          vscode.ViewColumn.Beside,
          {}
        );
        panel.webview.html = renderTraceHtml(result);
      } catch {
        vscode.window.showErrorMessage("ArchMAP trace: failed to parse output.");
      }
    }
  );
}

/**
 * @param {object} report
 * @param {string} root
 */
function applyDiagnostics(report, root) {
  diagnostics.clear();

  /** @type {Map<string, vscode.Diagnostic[]>} */
  const byFile = new Map();

  const addDiag = (file, message, severity) => {
    const absPath = path.isAbsolute(file) ? file : path.join(root, file.replace(/\//g, path.sep));
    const uri = vscode.Uri.file(absPath);
    const key = uri.toString();
    if (!byFile.has(key)) byFile.set(key, []);
    const diag = new vscode.Diagnostic(
      new vscode.Range(0, 0, 0, 0),
      `[ArchMAP] ${message}`,
      severity
    );
    diag.source = DIAGNOSTIC_SOURCE;
    byFile.get(key).push(diag);
  };

  // Circular dependencies
  const cycles = report.cycles ?? [];
  for (const cycle of cycles) {
    const files = Array.isArray(cycle) ? cycle : [];
    for (const file of files) {
      addDiag(file, `Circular dependency: ${files.join(" → ")}`, vscode.DiagnosticSeverity.Warning);
    }
  }

  // Layer violations
  const layerViolations = report.risks?.layer_violations ?? [];
  for (const v of layerViolations) {
    if (v.file) {
      addDiag(
        v.file,
        `Layer violation: ${v.fromLayer} → ${v.toLayer}`,
        vscode.DiagnosticSeverity.Warning
      );
    }
  }

  // God modules
  const godModules = report.risks?.god_modules ?? [];
  for (const g of godModules) {
    if (g.file) {
      addDiag(g.file, `God module (${g.incoming ?? "?"} dependents)`, vscode.DiagnosticSeverity.Information);
    }
  }

  // Custom rule violations
  const ruleViolations = report.architecture?.ruleViolations ?? [];
  for (const v of ruleViolations) {
    if (v.file) {
      addDiag(v.file, `Rule violation: ${v.from} → ${v.to}`, vscode.DiagnosticSeverity.Warning);
    }
  }

  for (const [key, diags] of byFile.entries()) {
    diagnostics.set(vscode.Uri.parse(key), diags);
  }
}

/**
 * @param {object} report
 */
function updateStatusBar(report) {
  const health = report.architecture?.health ?? {};
  const score = health.score ?? "?";
  const grade = health.grade ?? "";
  const cycles = report.metrics?.circularDependencyCount ?? 0;

  let icon = "$(graph)";
  if (typeof score === "number") {
    if (score >= 80) icon = "$(pass)";
    else if (score >= 50) icon = "$(warning)";
    else icon = "$(error)";
  }

  statusBar.text = `${icon} ArchMAP ${score}/100 (${grade})${cycles > 0 ? ` · ${cycles} cycles` : ""}`;
  statusBar.tooltip = "Click to re-analyze";
}

/**
 * @param {object} result
 * @returns {string}
 */
function renderTraceHtml(result) {
  const entry = result.entrypoint ?? "";
  const reachable = result.reachable ?? [];
  const unreachable = result.unreachable ?? [];
  const coverage = result.coveragePercent ?? 0;
  const error = result.error ?? "";

  if (error) {
    return `<html><body><p style="color:red">${error}</p></body></html>`;
  }

  const rows = reachable
    .map(
      (/** @type {{file:string,depth:number}} */ r) =>
        `<tr><td>${r.depth}</td><td>${r.file}</td></tr>`
    )
    .join("");

  const unreachableList = unreachable
    .map((/** @type {string} */ f) => `<li>${f}</li>`)
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family); font-size: 13px; padding: 16px; }
  h2 { margin-bottom: 4px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 4px 8px; text-align: left; border-bottom: 1px solid var(--vscode-panel-border); }
  th { background: var(--vscode-editor-background); }
  details { margin-top: 16px; }
  summary { cursor: pointer; font-weight: bold; }
</style>
</head>
<body>
<h2>Trace: ${entry}</h2>
<p>${reachable.length} reachable / ${reachable.length + unreachable.length} total (${coverage}% coverage)</p>
<table>
  <thead><tr><th>Depth</th><th>File</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
${unreachable.length > 0 ? `<details><summary>${unreachable.length} unreachable files</summary><ul>${unreachableList}</ul></details>` : ""}
</body>
</html>`;
}

function workspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function getExePath() {
  return (
    vscode.workspace.getConfiguration("archmap").get("executablePath") ?? "archmap"
  );
}

module.exports = { activate, deactivate };
