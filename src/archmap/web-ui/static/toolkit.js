/* ============================================================
   ArchMAP toolkit views (v1.4.0)
   Analysis-quality card, Findings, Task context, Inspect (static
   reverse engineering + Inspector canvas), and Security audit.
   app.js owns the graph and navigation; it hands this module a small
   host API through initToolkit().
   ============================================================ */

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const HEX_PAGE = 512;

let host = null;
const tk = {
  auditResult: null,
  inspectResult: null,
  inspectPath: "",
  hexOffset: 0,
  hexSize: 0,
  allStrings: null,
  linkageCy: null,
  findingsFilter: { domain: "all", severity: "info" },
};

/* ------------------------------------------------------------
   Host wiring
   ------------------------------------------------------------ */

export function initToolkit(api) {
  host = api;
  bindStaticControls();
}

const t = (key, vars) => {
  let text = host ? host.t(key) : key;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
  return text;
};
const esc = (v) => String(v ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#39;");

export function onViewShown(key, report) {
  if (key === "findings") renderFindings(report);
  if (key === "context") renderContextIdle();
  if (key === "inspect") renderInspectPanel();
  if (key === "audit") renderAudit();
}

export function onReportUpdated(report, activeView) {
  if (activeView) onViewShown(activeView, report);
}

export function onLanguageChanged(report, activeView) {
  if (activeView) onViewShown(activeView, report);
  if (tk.inspectResult && isInspectorVisible()) renderInspector();
}

async function postJson(path, payload) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    });
  } catch (err) {
    throw new Error(err.message || t("tkError"));
  }
  if (res.status === 404) throw new Error(t("tkUnavailable"));
  if (res.status === 403) throw new Error(t("tkNotLocal"));
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.status !== "success") throw new Error(data.message || `HTTP ${res.status}`);
  return data.result;
}

/** Inventory paths are relative to the inspected folder; the API wants project-relative. */
function inProject(relative) {
  const base = (tk.inspectPath || ".").replace(/\/+$/, "");
  return base === "." || base === "" ? relative : `${base}/${relative}`;
}

function humanSize(bytes) {
  let value = Number(bytes) || 0;
  for (const unit of ["B", "KB", "MB", "GB"]) {
    if (value < 1024 || unit === "GB") return unit === "B" ? `${value} B` : `${value.toFixed(1)} ${unit}`;
    value /= 1024;
  }
  return `${bytes} B`;
}

function errorBox(message) {
  return `<div class="tk-alert tk-alert-danger"><b>${esc(t("tkError"))}:</b> ${esc(message)}</div>`;
}

function sevBadge(severity) {
  const sev = SEVERITIES.includes(severity) ? severity : "info";
  return `<span class="tk-sev tk-sev-${sev}">${esc(t(`sev_${sev}`))}</span>`;
}

function findingItem(f, { linkable = true } = {}) {
  const target = f.file || f.source || "";
  const evidence = (f.evidence || []).map(e => `<li>${esc(e)}</li>`).join("");
  const conf = typeof f.confidence === "number" ? Math.round(f.confidence * 100) : null;
  const link = linkable && target && host?.hasNode(target)
    ? `<button type="button" class="ghost tk-link" data-focus="${esc(target)}">${esc(t("fShowInGraph"))}</button>`
    : "";
  return `
    <li class="tk-finding tk-border-${SEVERITIES.includes(f.severity) ? f.severity : "info"}">
      <div class="tk-finding-head">
        ${sevBadge(f.severity)}
        <span class="tk-id">${esc(f.id)}</span>
        ${conf !== null ? `<span class="tk-conf" title="${esc(t("fConfidence"))}">${conf}%</span>` : ""}
      </div>
      <p class="tk-finding-msg">${esc(f.message)}</p>
      ${evidence ? `<details class="tk-details"><summary>${esc(t("fEvidence"))}</summary><ul>${evidence}</ul></details>` : ""}
      ${link}
    </li>`;
}

function bindFocusLinks(container) {
  container.querySelectorAll("[data-focus]").forEach(btn => {
    btn.addEventListener("click", () => host.focusNode(btn.dataset.focus));
  });
}

/* ------------------------------------------------------------
   1. Analysis-quality card (Insights) and KPI
   ------------------------------------------------------------ */

export function renderQualityCard(report) {
  const q = report?.metrics?.analysisQuality;
  if (!q) return "";
  const level = q.confidenceLevel || "high";
  const pct = Math.round((q.confidence ?? 1) * 100);
  const skipped = (q.decodeFailureCount || 0) + (q.oversizedSkippedCount || 0);
  const langs = Object.entries(q.languages || {}).map(([lang, s]) => `
    <tr><td>${esc(lang)}</td><td>${s.files}</td><td>${Math.round((s.resolutionRate ?? 1) * 100)}%</td><td>${s.failures || 0}</td></tr>`).join("");
  const warnings = (q.warnings || []).length
    ? `<ul class="tk-warnings">${q.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>`
    : `<p class="tk-muted">${esc(t("qualNoWarnings"))}</p>`;
  const failures = (q.parseFailures || []).slice(0, 10).map(f =>
    `<li><span class="tk-mono">${esc(f.file)}</span> — ${esc(f.error)}</li>`).join("");
  return `
    <section class="card tk-quality tk-level-${esc(level)}">
      <div class="card-head">
        <span class="ico"><svg viewBox="0 0 24 24"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg></span>
        <h2>${esc(t("qualTitle"))}</h2>
        <span class="count-pill tk-level-pill">${esc(t(`qualLevel_${level}`))} · ${pct}%</span>
      </div>
      <div class="card-body">
        <p class="tk-explain">${esc(t("qualExplain"))}</p>
        <div class="tk-stat-grid">
          <div><span>${esc(t("qualParsed"))}</span><b>${q.filesParsed}/${q.filesDiscovered}</b></div>
          <div><span>${esc(t("qualResolution"))}</span><b>${Math.round((q.resolutionRate ?? 1) * 100)}%</b></div>
          <div><span>${esc(t("qualFailures"))}</span><b>${q.parseFailureCount || 0}</b></div>
          <div><span>${esc(t("qualSkipped"))}</span><b>${skipped}</b></div>
        </div>
        ${warnings}
        ${failures ? `<details class="tk-details"><summary>${esc(t("qualFailures"))}</summary><ul>${failures}</ul></details>` : ""}
        ${langs ? `<table class="tk-table"><thead><tr><th>${esc(t("qualByLang"))}</th><th>${esc(t("qualFiles"))}</th><th>${esc(t("qualResolution"))}</th><th>${esc(t("qualFailures"))}</th></tr></thead><tbody>${langs}</tbody></table>` : ""}
      </div>
    </section>`;
}

export function qualityKpi(report) {
  const q = report?.metrics?.analysisQuality;
  if (!q) return null;
  return { label: t("kpiConfidence"), value: `${Math.round((q.confidence ?? 1) * 100)}%`, warn: q.confidenceLevel !== "high" };
}

/* ------------------------------------------------------------
   2. Findings view
   ------------------------------------------------------------ */

function allFindings(report) {
  const base = Array.isArray(report?.findings) ? report.findings : [];
  const audit = tk.auditResult?.findings ?? [];
  return [...base, ...audit];
}

function renderFindings(report) {
  const container = document.getElementById("findingsContent");
  if (!container) return;
  const findings = allFindings(report);
  const domains = [...new Set(findings.map(f => f.domain))].sort();
  const domain = domains.includes(tk.findingsFilter.domain) ? tk.findingsFilter.domain : "all";
  const { severity } = tk.findingsFilter;
  const floor = SEVERITIES.indexOf(severity);
  const visible = findings
    .filter(f => domain === "all" || f.domain === domain)
    .filter(f => SEVERITIES.indexOf(f.severity) <= (floor < 0 ? 4 : floor))
    .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity));
  const counts = SEVERITIES.map(s => {
    const n = findings.filter(f => f.severity === s).length;
    return n ? `<span class="tk-count">${sevBadge(s)} ${n}</span>` : "";
  }).join("");

  container.innerHTML = `
    <section class="card">
      <div class="card-body">
        <div class="tk-counts">${counts || `<span class="tk-muted">${esc(t("fNone"))}</span>`}</div>
        <div class="tk-filter-row">
          <label class="field"><span>${esc(t("fDomain"))}</span>
            <select id="tkFindingsDomain">
              <option value="all">${esc(t("fAllDomains"))}</option>
              ${domains.map(d => `<option value="${esc(d)}" ${d === domain ? "selected" : ""}>${esc(t(`dom_${d}`))}</option>`).join("")}
            </select>
          </label>
          <label class="field"><span>${esc(t("fMinSeverity"))}</span>
            <select id="tkFindingsSeverity">
              ${[...SEVERITIES].reverse().map(s => `<option value="${s}" ${s === severity ? "selected" : ""}>${esc(s === "info" ? t("fAll") : t(`sev_${s}`))}</option>`).join("")}
            </select>
          </label>
        </div>
        ${tk.auditResult ? "" : `<p class="tk-muted tk-small">${esc(t("fAuditHint"))}</p>`}
      </div>
    </section>
    <section class="card">
      <div class="card-head"><h2>${esc(t("findingsTitle"))}</h2><span class="count-pill">${visible.length}</span></div>
      ${visible.length
        ? `<ul class="tk-findings">${visible.map(f => findingItem(f)).join("")}</ul>`
        : `<p class="selection-muted tk-pad">${esc(t("fNone"))}</p>`}
    </section>`;

  document.getElementById("tkFindingsDomain")?.addEventListener("change", (e) => { tk.findingsFilter.domain = e.target.value; renderFindings(report); });
  document.getElementById("tkFindingsSeverity")?.addEventListener("change", (e) => {
    tk.findingsFilter.severity = e.target.value;
    renderFindings(report);
  });
  bindFocusLinks(container);
}

/* ------------------------------------------------------------
   3. Task context view
   ------------------------------------------------------------ */

function renderContextIdle() {
  const container = document.getElementById("contextContent");
  if (container && !container.dataset.filled) {
    container.innerHTML = `<p class="selection-muted tk-pad">${esc(t("ctxHowItWorks"))}</p>`;
  }
}

async function runContext() {
  const input = document.getElementById("tkContextTask");
  const budget = Number(document.getElementById("tkContextBudget")?.value || 8000);
  const btn = document.getElementById("tkContextRun");
  const container = document.getElementById("contextContent");
  const task = (input?.value || "").trim();
  if (!task || !container) return;
  btn.disabled = true;
  btn.textContent = t("ctxRunning");
  try {
    const result = await postJson("/api/context", { task, budget });
    container.dataset.filled = "1";
    renderContextResult(result, container);
  } catch (err) {
    container.innerHTML = errorBox(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = t("ctxRun");
  }
}

function renderContextResult(result, container) {
  if (!result.files?.length) {
    container.innerHTML = `<p class="selection-muted tk-pad">${esc(result.note || t("ctxEmpty"))}</p>`;
    return;
  }
  const items = result.files.map((f, i) => `
    <li class="tk-ctx-item">
      <div class="tk-ctx-head">
        <span class="tk-rank">${i + 1}</span>
        <button type="button" class="tk-file-link" data-focus="${esc(f.file)}">${esc(f.file)}</button>
        <span class="tk-role tk-role-${f.role}">${esc(t(f.role === "match" ? "ctxMatch" : "ctxNeighbor"))}</span>
      </div>
      <p class="tk-ctx-meta">~${f.estimatedTokens} ${esc(t("ctxTokens"))} · ${f.dependents} ${esc(t("ctxDependents"))}</p>
      ${(f.reasons || []).slice(0, 3).map(r => `<p class="tk-reason">${esc(r)}</p>`).join("")}
      ${(f.snippets || []).length ? `<pre class="tk-snippets">${f.snippets.map(s => `<span class="tk-ln">L${s.line}</span> ${esc(s.text)}`).join("\n")}</pre>` : ""}
    </li>`).join("");
  container.innerHTML = `
    <section class="card">
      <div class="card-head">
        <h2>${esc(t("ctxSummary", { n: result.files.length, used: result.usedTokens, budget: result.budgetTokens }))}</h2>
      </div>
      <div class="card-body">
        <button type="button" id="tkCtxHighlight" class="primary tk-full">${esc(t("ctxHighlightAll"))}</button>
        <p class="tk-muted tk-small">${esc(t("ctxHowItWorks"))}</p>
      </div>
      <ol class="tk-ctx-list">${items}</ol>
    </section>`;
  bindFocusLinks(container);
  document.getElementById("tkCtxHighlight")?.addEventListener("click", () => {
    host.highlightFiles(result.files.map(f => f.file));
  });
}

/* ------------------------------------------------------------
   4. Inspect view (left panel) + Inspector canvas
   ------------------------------------------------------------ */

function renderInspectPanel() {
  const container = document.getElementById("inspectContent");
  if (!container) return;
  if (!tk.inspectResult) {
    container.innerHTML = `<p class="selection-muted tk-pad">${esc(t("rvHint"))}</p>`;
    return;
  }
  const r = tk.inspectResult;
  container.innerHTML = r.kind === "directory" ? inventorySummary(r) : fileSummary(r);
  container.querySelectorAll("[data-inspect]").forEach(btn => {
    btn.addEventListener("click", () => runInspect(btn.dataset.inspect));
  });
  document.getElementById("tkOpenInspector")?.addEventListener("click", () => host.switchCanvasTab("inspector"));
}

export async function runInspect(path) {
  const input = document.getElementById("tkInspectPath");
  const target = (path ?? input?.value ?? ".").trim() || ".";
  if (input) input.value = target;
  const btn = document.getElementById("tkInspectRun");
  const container = document.getElementById("inspectContent");
  if (btn) { btn.disabled = true; btn.textContent = t("rvRunning"); }
  try {
    const withStrings = document.getElementById("tkInspectStrings")?.checked ?? true;
    tk.inspectResult = await postJson("/api/inspect", { path: target, strings: withStrings });
    tk.inspectPath = tk.inspectResult.kind === "file" ? tk.inspectResult.relativePath : target;
    tk.hexOffset = 0;
    tk.allStrings = null;
    renderInspectPanel();
    document.getElementById("canvasTabInspector")?.removeAttribute("hidden");
    host.switchCanvasTab("inspector");
  } catch (err) {
    if (container) container.innerHTML = errorBox(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t("rvRun"); }
  }
}

function kv(label, value) {
  return value === undefined || value === null || value === ""
    ? ""
    : `<div class="tk-kv"><span>${esc(label)}</span><b>${value}</b></div>`;
}

function hardeningChips(hardening) {
  if (!hardening) return "";
  return `<div class="tk-chips">${Object.entries(hardening).map(([key, value]) => {
    if (value === null || value === undefined) return "";
    const good = typeof value === "boolean"
      ? (key === "stackExecutable" || key === "stripped" ? !value : value)
      : !["no", "none"].includes(String(value));
    const label = typeof value === "boolean" ? key : `${key}: ${value}`;
    return `<span class="tk-chip ${good ? "tk-chip-ok" : "tk-chip-bad"}">${esc(label)}</span>`;
  }).join("")}</div>`;
}

function detailRows(r) {
  const d = r.details || {};
  const fmt = r.format?.format;
  if (fmt === "elf") {
    return kv("Header", esc(`${d.class} ${d.machine} ${d.type}`))
      + kv("Entry", esc(d.entryPoint)) + kv("Interpreter", esc(d.interpreter))
      + kv(t("rvLibraries"), esc((d.neededLibraries || []).join(", ") || "—"))
      + kv("Symbols", esc(`${d.importedSymbolCount} imported · ${d.exportedSymbolCount} exported`))
      + kv("Language", esc(d.language));
  }
  if (fmt === "pe") {
    return kv("Header", esc(`${d.format} ${d.machine} ${d.kind} · ${d.subsystem}`))
      + kv("Compiled", esc(d.compiledAt)) + kv(".NET", d.dotnet ? "yes" : "")
      + kv(t("rvLibraries"), esc((d.importedLibraries || []).join(", ") || "—"))
      + kv("Imports", esc(d.importedFunctionCount)) + kv("Exports", esc(d.exports?.nameCount))
      + kv("Packer", esc((d.packers || []).join(", ")));
  }
  if (fmt === "macho" || fmt === "macho-fat") {
    const images = d.universal ? (d.architectures || []).map(a => a.image).filter(Boolean) : [d];
    return images.map(img => kv("Image", esc(`${img.class} ${img.cpu} ${img.fileType}`))
      + kv(t("rvLibraries"), esc((img.linkedLibraries || []).map(l => l.name).join(", ") || "—"))).join("");
  }
  if (fmt === "wasm") {
    return kv("Imports", esc(`${(d.imports || []).length} from ${(d.importModules || []).join(", ") || "—"}`))
      + kv("Exports", esc((d.exports || []).length)) + kv("Functions", esc(d.definedFunctionCount))
      + kv("Toolchain", esc(d.toolchain));
  }
  return "";
}

function dataSummary(data) {
  if (!data) return "";
  if (data.error) return `<p class="tk-muted">${esc(data.error)}</p>`;
  let body = "";
  if (data.kind === "sqlite") {
    body = `<table class="tk-table"><tbody>${data.tables.map(tb =>
      `<tr><td class="tk-mono">${esc(tb.name)}</td><td>${tb.type === "table" ? esc(tb.rows) + " rows" : "view"}</td><td>${esc(tb.columns.map(c => `${c.name}:${c.type}`).join(", "))}</td></tr>`).join("")}</tbody></table>`;
  } else if (data.kind === "csv") {
    body = kv("Rows", esc(data.rows)) + `<div class="tk-chips">${data.columns.map(c => `<span class="tk-chip">${esc(c.name)}: ${esc(c.type)}</span>`).join("")}</div>`;
  } else if (data.kind === "json" || data.kind === "jsonl") {
    body = `<pre class="tk-snippets">${esc(JSON.stringify(data.schema, null, 2)).slice(0, 4000)}</pre>`;
  } else if (data.kind === "tar") {
    body = kv("Members", esc(data.members)) + kv("Size", esc(humanSize(data.totalSize)));
  } else if (data.kind === "gzip") {
    body = kv("Original name", esc(data.originalName)) + kv("Uncompressed", esc(humanSize(data.uncompressedSizeMod32)));
  } else {
    body = kv("Entries", esc(data.entries)) + kv("Uncompressed", esc(humanSize(data.uncompressedSize)))
      + kv("Ratio", esc(`${data.compressionRatio}:1`));
    if (data.android) {
      body += kv("DEX", esc(data.android.dexFiles.join(", ") || "—")) + kv("ABIs", esc(data.android.abis.join(", ") || "—"));
    }
  }
  return `<div class="tk-block"><h3>${esc(t("rvData"))}</h3>${body}</div>`;
}

function fileSummary(r) {
  const d = r.details || {};
  const hardening = d.hardening || (d.universal ? d.architectures?.[0]?.image?.hardening : null);
  const limitations = (r.limitations || []).map(l => `<li>${esc(l)}</li>`).join("");
  return `
    <section class="card">
      <div class="card-head"><h2 class="tk-mono tk-ellipsis" title="${esc(r.relativePath)}">${esc(r.relativePath || r.name)}</h2></div>
      <div class="card-body">
        ${kv(t("rvType"), esc(`${r.format.description} (${r.format.format})`))}
        ${kv(t("rvSize"), esc(humanSize(r.size)))}
        ${kv(t("rvEntropy"), esc(`${r.entropy.overall} · ${r.entropy.classification}`))}
        ${kv(t("rvSha256"), `<span class="tk-mono tk-break">${esc(r.hashes.sha256)}</span>`)}
        ${detailRows(r)}
        ${hardening ? `<div class="tk-block"><h3>${esc(t("rvHardening"))}</h3>${hardeningChips(hardening)}</div>` : ""}
        ${dataSummary(r.data)}
        ${(r.errors || []).map(e => `<div class="tk-alert">${esc(e)}</div>`).join("")}
        <button type="button" id="tkOpenInspector" class="primary tk-full">${esc(t("rvOpenInspector"))}</button>
      </div>
    </section>
    <section class="card">
      <div class="card-head"><h2>${esc(t("rvFindings"))}</h2><span class="count-pill">${r.findings.length}</span></div>
      ${r.findings.length ? `<ul class="tk-findings">${r.findings.map(f => findingItem(f, { linkable: false })).join("")}</ul>` : `<p class="selection-muted tk-pad">${esc(t("rvNoFindings"))}</p>`}
    </section>
    ${limitations ? `<details class="tk-details tk-pad"><summary>${esc(t("rvLimitations"))}</summary><ul>${limitations}</ul></details>` : ""}`;
}

function inventorySummary(r) {
  const formats = Object.entries(r.byFormat || {}).map(([k, v]) => `<span class="tk-chip">${esc(k)} ${v}</span>`).join("");
  const binaries = (r.binaries || []).slice(0, 200).map(b => `
    <li class="list-item" data-inspect="${esc(inProject(b.file))}">
      <div class="list-main"><span class="list-name">${esc(b.file)}</span>
        <span class="list-meta">${esc(b.format)} · ${esc((b.libraries || []).slice(0, 4).join(", ") || "—")}</span></div>
      ${b.findingCount ? `<span class="list-stat warn">${b.findingCount}</span>` : ""}
    </li>`).join("");
  return `
    <section class="card">
      <div class="card-head"><h2>${esc(t("rvInventory", { files: r.filesScanned, size: humanSize(r.totalSize) }))}</h2></div>
      <div class="card-body"><div class="tk-chips">${formats}</div>
        <button type="button" id="tkOpenInspector" class="primary tk-full">${esc(t("rvLinkage"))}</button></div>
    </section>
    <section class="card">
      <div class="card-head"><h2>${esc(t("rvBinaries"))}</h2><span class="count-pill">${(r.binaries || []).length}</span></div>
      ${binaries ? `<ol class="list">${binaries}</ol>` : `<p class="selection-muted tk-pad">—</p>`}
    </section>
    <section class="card">
      <div class="card-head"><h2>${esc(t("rvFindings"))}</h2><span class="count-pill">${r.findings.length}</span></div>
      ${r.findings.length ? `<ul class="tk-findings">${r.findings.slice(0, 100).map(f => findingItem(f, { linkable: false })).join("")}</ul>` : `<p class="selection-muted tk-pad">${esc(t("rvNoFindings"))}</p>`}
    </section>`;
}

function isInspectorVisible() {
  return !document.getElementById("inspectorView")?.classList.contains("canvas-view-hidden");
}

export function renderInspector() {
  const root = document.getElementById("inspectorView");
  if (!root) return;
  const r = tk.inspectResult;
  if (!r) {
    root.innerHTML = `<p class="selection-muted tk-pad">${esc(t("rvHint"))}</p>`;
    return;
  }
  if (r.kind === "directory") {
    root.innerHTML = `
      <div class="tk-inspector-head"><h3>${esc(t("rvLinkage"))}</h3>
        <p class="tk-muted">${esc(t("rvLinkageExplain"))}</p></div>
      <div id="tkLinkageCy" class="tk-linkage"></div>
      <div class="tk-inspector-section"><h3>${esc(t("rvMostLinked"))}</h3>
        <ol class="tk-mostlinked">${(r.mostLinkedLibraries || []).map(m => `<li><span class="tk-mono">${esc(m.library)}</span> <b>${m.dependents}</b></li>`).join("")}</ol></div>`;
    renderLinkageGraph(r);
    return;
  }
  root.innerHTML = `
    <div class="tk-inspector-head">
      <h3 class="tk-mono">${esc(r.relativePath)}</h3>
      <p class="tk-muted">${esc(r.format.description)} · ${esc(humanSize(r.size))}</p>
    </div>
    <div class="tk-inspector-section">
      <h3>${esc(t("entTitle"))}</h3>
      <p class="tk-muted tk-small">${esc(t("entExplain"))}</p>
      ${entropyChart(r.entropy)}
    </div>
    <div class="tk-inspector-section">
      <div class="tk-hex-toolbar">
        <h3>${esc(t("hxTitle"))}</h3>
        <label class="tk-inline">${esc(t("hxOffset"))}<input id="tkHexOffset" type="text" value="0x0" spellcheck="false" /></label>
        <button type="button" id="tkHexGo">${esc(t("hxGo"))}</button>
        <button type="button" id="tkHexPrev">${esc(t("hxPrev"))}</button>
        <button type="button" id="tkHexNext">${esc(t("hxNext"))}</button>
        <button type="button" id="tkHexEnd">${esc(t("hxEnd"))}</button>
      </div>
      <pre id="tkHexdump" class="tk-hexdump">…</pre>
    </div>
    <div class="tk-inspector-section">
      <div class="tk-hex-toolbar">
        <h3>${esc(t("stTitle"))}</h3>
        <input id="tkStringsFilter" type="search" placeholder="${esc(t("stFilter"))}" />
        <label class="switch tk-inline"><input id="tkStringsInteresting" type="checkbox" checked /><span>${esc(t("stInteresting"))}</span></label>
      </div>
      <div id="tkStrings"></div>
    </div>`;
  document.getElementById("tkHexGo")?.addEventListener("click", () => loadHex(parseOffset(document.getElementById("tkHexOffset").value)));
  document.getElementById("tkHexOffset")?.addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("tkHexGo").click(); });
  document.getElementById("tkHexPrev")?.addEventListener("click", () => loadHex(Math.max(0, tk.hexOffset - HEX_PAGE)));
  document.getElementById("tkHexNext")?.addEventListener("click", () => loadHex(tk.hexOffset + HEX_PAGE));
  document.getElementById("tkHexEnd")?.addEventListener("click", () => loadHex(-HEX_PAGE));
  document.getElementById("tkStringsFilter")?.addEventListener("input", renderStrings);
  document.getElementById("tkStringsInteresting")?.addEventListener("change", async (e) => {
    if (!e.target.checked && !tk.allStrings) {
      try {
        const res = await postJson("/api/strings", { path: tk.inspectPath, interesting: false, limit: 5000 });
        tk.allStrings = res.strings;
      } catch (err) {
        document.getElementById("tkStrings").innerHTML = errorBox(err.message);
        return;
      }
    }
    renderStrings();
  });
  // Entropy blocks jump the hexdump to their offset.
  root.querySelectorAll("[data-offset]").forEach(bar => bar.addEventListener("click", () => loadHex(Number(bar.dataset.offset))));
  loadHex(tk.hexOffset);
  renderStrings();
}

function parseOffset(text) {
  const value = String(text || "0").trim();
  const parsed = /^-?0x/i.test(value) ? parseInt(value.replace(/^(-?)0x/i, "$1"), 16) : parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

async function loadHex(offset) {
  const pre = document.getElementById("tkHexdump");
  if (!pre || !tk.inspectPath) return;
  try {
    const res = await postJson("/api/hexdump", { path: tk.inspectPath, offset, length: HEX_PAGE });
    tk.hexOffset = res.offset;
    tk.hexSize = res.size;
    pre.textContent = res.hexdump;
    const input = document.getElementById("tkHexOffset");
    if (input) input.value = `0x${res.offset.toString(16)}`;
    const next = document.getElementById("tkHexNext");
    if (next) next.disabled = res.offset + HEX_PAGE >= res.size;
    const prev = document.getElementById("tkHexPrev");
    if (prev) prev.disabled = res.offset === 0;
  } catch (err) {
    pre.textContent = `${t("tkError")}: ${err.message}`;
  }
}

function renderStrings() {
  const box = document.getElementById("tkStrings");
  if (!box || !tk.inspectResult) return;
  const interestingOnly = document.getElementById("tkStringsInteresting")?.checked ?? true;
  const needle = (document.getElementById("tkStringsFilter")?.value || "").toLowerCase();
  const source = interestingOnly
    ? (tk.inspectResult.strings?.interesting || [])
    : (tk.allStrings || []).map(s => ({ ...s, categories: [] }));
  const rows = source.filter(s => !needle || s.value.toLowerCase().includes(needle)).slice(0, 1000);
  if (!rows.length) {
    box.innerHTML = `<p class="tk-muted">${esc(t("stNone"))}</p>`;
    return;
  }
  box.innerHTML = `<table class="tk-table tk-strings"><tbody>${rows.map(s => `
    <tr><td class="tk-mono tk-off"><button type="button" class="tk-off-link" data-offset="${s.offset}">0x${s.offset.toString(16).padStart(8, "0")}</button></td>
      <td>${(s.categories || []).map(c => `<span class="tk-chip tk-chip-sm">${esc(c)}</span>`).join("")}</td>
      <td class="tk-mono tk-break">${esc(s.value)}</td></tr>`).join("")}</tbody></table>`;
  box.querySelectorAll("[data-offset]").forEach(btn => btn.addEventListener("click", () => {
    loadHex(Number(btn.dataset.offset) & ~0xf);
    document.getElementById("tkHexdump")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }));
}

function entropyChart(entropy) {
  const profile = entropy?.profile || [];
  if (!profile.length) return `<p class="tk-muted">—</p>`;
  const width = 100 / profile.length;
  const bars = profile.map((p, i) => {
    const h = Math.max(1, (p.entropy / 8) * 100);
    const cls = p.entropy >= 7.2 ? "tk-ent-high" : p.entropy <= 1 ? "tk-ent-low" : "tk-ent-mid";
    return `<rect class="${cls}" data-offset="${p.offset}" x="${i * width}" y="${100 - h}" width="${Math.max(width - 0.3, 0.2)}" height="${h}"><title>0x${p.offset.toString(16)} · ${p.entropy}</title></rect>`;
  }).join("");
  return `<svg class="tk-entropy" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="${esc(t("entTitle"))}">
    <line x1="0" y1="${100 - (7.2 / 8) * 100}" x2="100" y2="${100 - (7.2 / 8) * 100}" class="tk-ent-threshold"/>${bars}</svg>`;
}

function renderLinkageGraph(r) {
  const container = document.getElementById("tkLinkageCy");
  if (!container || typeof window.cytoscape !== "function") return;
  if (tk.linkageCy) { tk.linkageCy.destroy(); tk.linkageCy = null; }
  const nodes = (r.graph?.nodes || []).slice(0, 600);
  const ids = new Set(nodes.map(n => n.id));
  const edges = (r.graph?.edges || []).filter(e => ids.has(e.source) && ids.has(e.target));
  const style = getComputedStyle(document.documentElement);
  tk.linkageCy = window.cytoscape({
    container,
    elements: [
      ...nodes.map(n => ({ data: { id: n.id, label: n.id.replace(/^lib:/, "").split("/").pop(), kind: n.type } })),
      ...edges.map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target } })),
    ],
    style: [
      { selector: "node", style: { label: "data(label)", "font-size": 9, color: style.getPropertyValue("--ink").trim() || "#222", "text-valign": "bottom", "text-margin-y": 3, width: 14, height: 14 } },
      { selector: 'node[kind = "binary"]', style: { "background-color": "#6173e0", shape: "round-rectangle" } },
      { selector: 'node[kind = "library"]', style: { "background-color": "#62b386" } },
      { selector: "edge", style: { width: 1, "line-color": "#c4cad5", "target-arrow-color": "#c4cad5", "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7 } },
    ],
    maxZoom: 1.6,
    layout: { name: "cose", animate: false, fit: true, padding: 40, nodeRepulsion: 6000 },
  });
  tk.linkageCy.on("tap", 'node[kind = "binary"]', (e) => runInspect(inProject(e.target.id())));
}

/* ------------------------------------------------------------
   5. Security audit view
   ------------------------------------------------------------ */

function renderAudit() {
  const container = document.getElementById("auditContent");
  if (!container) return;
  const r = tk.auditResult;
  if (!r) {
    container.innerHTML = `<p class="selection-muted tk-pad">${esc(t("auHint"))}</p>`;
    return;
  }
  const notes = (r.limitations || []).map(n => `<li>${esc(n)}</li>`).join("");
  container.innerHTML = `
    <section class="card">
      <div class="card-body">
        <div class="tk-stat-grid">
          <div><span>${esc(t("auSecrets"))}</span><b>${r.secretFindings}</b></div>
          <div><span>${esc(t("auCode"))}</span><b>${Number(r.codeFindings || 0)}</b></div>
          <div><span>${esc(t("auAgent"))}</span><b>${r.agentFindings}</b></div>
        </div>
        <p class="tk-muted tk-small">${esc(t("auFiles", { n: r.filesScanned }))} · ${esc(r.gitAware ? t("auGitAware") : t("auNotGit"))}</p>
      </div>
    </section>
    <section class="card">
      <div class="card-head"><h2>${esc(t("findingsTitle"))}</h2><span class="count-pill">${r.findings.length}</span></div>
      ${r.findings.length
        ? `<ul class="tk-findings">${[...r.findings].sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity)).map(f => findingItem(f, { linkable: false })).join("")}</ul>`
        : `<p class="selection-muted tk-pad">${esc(t("auClean"))}</p>`}
    </section>
    ${notes ? `<details class="tk-details tk-pad"><summary>${esc(t("auNotes"))}</summary><ul>${notes}</ul></details>` : ""}`;
}

async function runAudit() {
  const btn = document.getElementById("tkAuditRun");
  const container = document.getElementById("auditContent");
  if (btn) { btn.disabled = true; btn.textContent = t("auRunning"); }
  try {
    tk.auditResult = await postJson("/api/audit", {});
    renderAudit();
  } catch (err) {
    if (container) container.innerHTML = errorBox(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t("auRun"); }
  }
}

/* ------------------------------------------------------------
   Static controls (rendered in index.html)
   ------------------------------------------------------------ */

function bindStaticControls() {
  document.getElementById("tkContextRun")?.addEventListener("click", runContext);
  document.getElementById("tkContextTask")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runContext();
  });
  document.getElementById("tkInspectRun")?.addEventListener("click", () => runInspect());
  document.getElementById("tkInspectPath")?.addEventListener("keydown", (e) => { if (e.key === "Enter") runInspect(); });
  document.getElementById("tkAuditRun")?.addEventListener("click", runAudit);
}

/* ------------------------------------------------------------
   Translations (merged into app.js's table)
   ------------------------------------------------------------ */

export const TOOLKIT_TRANSLATIONS = {
  en: {
    navFindings:"Findings",navContext:"Task context",navInspect:"Inspect files",navAudit:"Security audit",
    tkError:"Error",tkUnavailable:"This server doesn't support this feature. Run `archmap serve` from ArchMAP 1.4.0 or later.",tkNotLocal:"Only available when the UI is opened from localhost.",
    qualTitle:"Analysis confidence",qualExplain:"How much of the project made it into the graph. Below 'high', 'no dependents' and small blast radii are lower bounds.",qualParsed:"Files parsed",qualResolution:"Import resolution",qualFailures:"Parse failures",qualSkipped:"Skipped (encoding/size)",qualByLang:"Language",qualFiles:"Files",qualNoWarnings:"No gaps: every discovered source file was parsed.",qualLevel_high:"High",qualLevel_medium:"Medium",qualLevel_low:"Low",kpiConfidence:"Confidence",
    findingsTitle:"Findings",findingsSub:"Every problem ArchMAP found, with a stable ID, severity, confidence and evidence.",fDomain:"Domain",fAllDomains:"All domains",fMinSeverity:"Minimum severity",fAll:"All",fNone:"No findings match these filters.",fEvidence:"Evidence",fConfidence:"Confidence",fShowInGraph:"Show in graph",fAuditHint:"Run the Security audit to add secret (SEC-*) and agent-config (AGENT-*) findings here.",
    dom_code:"Code architecture",dom_quality:"Analysis quality",dom_security:"Secrets",dom_agent:"Agent configuration",dom_binary:"Binaries & files",dom_network:"Network",
    sev_critical:"Critical",sev_high:"High",sev_medium:"Medium",sev_low:"Low",sev_info:"Info",
    ctxTitle:"Task context",ctxSub:"Describe a task and get the files to read, in order, within a token budget.",ctxPlaceholder:"e.g. fix retry backoff in the payment webhook",ctxBudget:"Token budget",ctxRun:"Find files",ctxRunning:"Ranking…",ctxEmpty:"No files matched. Use names of functions, classes or files.",ctxSummary:"{n} files · ~{used} of {budget} tokens",ctxMatch:"match",ctxNeighbor:"neighbor",ctxTokens:"tokens",ctxDependents:"dependents",ctxHighlightAll:"Highlight in graph",ctxHowItWorks:"Ranked with BM25 over code identifiers. 'Neighbor' files don't mention the task but import, or are imported by, a match. Ctrl+Enter runs the search.",
    rvTitle:"Inspect files",rvSub:"Static reverse engineering of any file or folder in the project: binaries, archives, databases, data. Nothing is executed.",rvPathPlaceholder:"Path inside the project (e.g. bin/app or .)",rvRun:"Inspect",rvRunning:"Inspecting…",rvStrings:"Extract strings",rvHint:"Enter a file path, or '.' to inventory the whole project and map which binaries link which libraries.",rvType:"Type",rvSize:"Size",rvSha256:"SHA-256",rvEntropy:"Entropy",rvHardening:"Mitigations",rvLibraries:"Libraries",rvData:"Data summary",rvFindings:"Findings",rvNoFindings:"No findings.",rvOpenInspector:"Open hexdump & strings",rvLimitations:"Limitations",rvBinaries:"Binaries & containers",rvInventory:"{files} files · {size}",rvMostLinked:"Most linked libraries",rvLinkage:"Linkage graph",rvLinkageExplain:"Binaries (blue) and the libraries they load (green). Click a binary to inspect it.",
    inspectorTab:"Inspector",hxTitle:"Hexdump",hxOffset:"Offset",hxGo:"Go",hxPrev:"◀ Prev",hxNext:"Next ▶",hxEnd:"End",stTitle:"Strings",stFilter:"Filter strings…",stInteresting:"Interesting only",stNone:"No strings to show.",entTitle:"Entropy profile",entExplain:"Bits per byte along the file (click a bar to jump the hexdump there). Near 8 = compressed or encrypted; near 0 = padding.",
    auTitle:"Security audit",auSub:"Committed secrets and risky AI-agent configuration: MCP servers, permissions, hooks, hidden Unicode. Offline; secret values are always redacted.",auRun:"Run audit",auRunning:"Auditing…",auSecrets:"Secrets",auCode:"Code",auAgent:"Agent config",auFiles:"{n} text files scanned",auGitAware:"git-aware",auNotGit:"not a git repository",auClean:"No secrets or risky agent configuration found.",auNotes:"Notes",auHint:"Run the audit to scan this project for secrets and AI-agent configuration risks.",
  },
  pt: {
    navFindings:"Findings",navContext:"Contexto da tarefa",navInspect:"Inspecionar arquivos",navAudit:"Auditoria de segurança",
    tkError:"Erro",tkUnavailable:"Este servidor não suporta este recurso. Use `archmap serve` do ArchMAP 1.4.0 ou superior.",tkNotLocal:"Disponível apenas quando a interface é aberta via localhost.",
    qualTitle:"Confiança da análise",qualExplain:"Quanto do projeto entrou no grafo. Abaixo de 'alta', 'sem dependentes' e raios de impacto pequenos são limites inferiores.",qualParsed:"Arquivos parseados",qualResolution:"Resolução de imports",qualFailures:"Falhas de parse",qualSkipped:"Ignorados (codificação/tamanho)",qualByLang:"Linguagem",qualFiles:"Arquivos",qualNoWarnings:"Sem lacunas: todo arquivo-fonte encontrado foi parseado.",qualLevel_high:"Alta",qualLevel_medium:"Média",qualLevel_low:"Baixa",kpiConfidence:"Confiança",
    findingsTitle:"Findings",findingsSub:"Todo problema encontrado, com ID estável, severidade, confiança e evidências.",fDomain:"Domínio",fAllDomains:"Todos os domínios",fMinSeverity:"Severidade mínima",fAll:"Todas",fNone:"Nenhum finding com esses filtros.",fEvidence:"Evidências",fConfidence:"Confiança",fShowInGraph:"Mostrar no grafo",fAuditHint:"Execute a Auditoria de segurança para incluir findings de segredos (SEC-*) e configuração de agentes (AGENT-*).",
    dom_code:"Arquitetura do código",dom_quality:"Qualidade da análise",dom_security:"Segredos",dom_agent:"Configuração de agentes",dom_binary:"Binários e arquivos",dom_network:"Rede",
    sev_critical:"Crítica",sev_high:"Alta",sev_medium:"Média",sev_low:"Baixa",sev_info:"Info",
    ctxTitle:"Contexto da tarefa",ctxSub:"Descreva uma tarefa e receba os arquivos a ler, em ordem, dentro de um orçamento de tokens.",ctxPlaceholder:"ex.: corrigir o retry com backoff no webhook de pagamento",ctxBudget:"Orçamento de tokens",ctxRun:"Encontrar arquivos",ctxRunning:"Ranqueando…",ctxEmpty:"Nenhum arquivo encontrado. Use nomes de funções, classes ou arquivos.",ctxSummary:"{n} arquivos · ~{used} de {budget} tokens",ctxMatch:"match",ctxNeighbor:"vizinho",ctxTokens:"tokens",ctxDependents:"dependentes",ctxHighlightAll:"Destacar no grafo",ctxHowItWorks:"Ranqueado com BM25 sobre identificadores do código. Arquivos 'vizinhos' não citam a tarefa, mas importam ou são importados por um match. Ctrl+Enter executa a busca.",
    rvTitle:"Inspecionar arquivos",rvSub:"Engenharia reversa estática de qualquer arquivo ou pasta do projeto: binários, compactados, bancos de dados, dados. Nada é executado.",rvPathPlaceholder:"Caminho dentro do projeto (ex.: bin/app ou .)",rvRun:"Inspecionar",rvRunning:"Inspecionando…",rvStrings:"Extrair strings",rvHint:"Informe o caminho de um arquivo, ou '.' para inventariar o projeto e mapear quais binários carregam quais bibliotecas.",rvType:"Tipo",rvSize:"Tamanho",rvSha256:"SHA-256",rvEntropy:"Entropia",rvHardening:"Mitigações",rvLibraries:"Bibliotecas",rvData:"Resumo dos dados",rvFindings:"Findings",rvNoFindings:"Nenhum finding.",rvOpenInspector:"Abrir hexdump e strings",rvLimitations:"Limitações",rvBinaries:"Binários e contêineres",rvInventory:"{files} arquivos · {size}",rvMostLinked:"Bibliotecas mais usadas",rvLinkage:"Grafo de bibliotecas",rvLinkageExplain:"Binários (azul) e as bibliotecas que carregam (verde). Clique em um binário para inspecioná-lo.",
    inspectorTab:"Inspector",hxTitle:"Hexdump",hxOffset:"Offset",hxGo:"Ir",hxPrev:"◀ Anterior",hxNext:"Próximo ▶",hxEnd:"Fim",stTitle:"Strings",stFilter:"Filtrar strings…",stInteresting:"Só as relevantes",stNone:"Nenhuma string para mostrar.",entTitle:"Perfil de entropia",entExplain:"Bits por byte ao longo do arquivo (clique numa barra para levar o hexdump até lá). Perto de 8 = comprimido ou criptografado; perto de 0 = preenchimento.",
    auTitle:"Auditoria de segurança",auSub:"Segredos commitados e configuração arriscada de agentes de IA: servidores MCP, permissões, hooks, Unicode oculto. Offline; valores secretos sempre ocultados.",auRun:"Executar auditoria",auRunning:"Auditando…",auSecrets:"Segredos",auCode:"Código",auAgent:"Config. de agentes",auFiles:"{n} arquivos de texto verificados",auGitAware:"considera o git",auNotGit:"não é um repositório git",auClean:"Nenhum segredo ou configuração arriscada de agentes encontrado.",auNotes:"Observações",auHint:"Execute a auditoria para procurar segredos e riscos de configuração de agentes de IA neste projeto.",
  },
  es: {
    navFindings:"Hallazgos",navContext:"Contexto de tarea",navInspect:"Inspeccionar archivos",navAudit:"Auditoría de seguridad",
    tkError:"Error",tkUnavailable:"Este servidor no admite esta función. Usa `archmap serve` de ArchMAP 1.4.0 o superior.",tkNotLocal:"Solo disponible cuando la interfaz se abre desde localhost.",
    qualTitle:"Confianza del análisis",qualExplain:"Cuánto del proyecto entró en el grafo. Por debajo de 'alta', 'sin dependientes' y radios de impacto pequeños son cotas inferiores.",qualParsed:"Archivos analizados",qualResolution:"Resolución de imports",qualFailures:"Fallos de análisis",qualSkipped:"Omitidos (codificación/tamaño)",qualByLang:"Lenguaje",qualFiles:"Archivos",qualNoWarnings:"Sin huecos: se analizaron todos los archivos fuente encontrados.",qualLevel_high:"Alta",qualLevel_medium:"Media",qualLevel_low:"Baja",kpiConfidence:"Confianza",
    findingsTitle:"Hallazgos",findingsSub:"Cada problema encontrado, con ID estable, severidad, confianza y evidencia.",fDomain:"Dominio",fAllDomains:"Todos los dominios",fMinSeverity:"Severidad mínima",fAll:"Todas",fNone:"Ningún hallazgo coincide con estos filtros.",fEvidence:"Evidencia",fConfidence:"Confianza",fShowInGraph:"Ver en el grafo",fAuditHint:"Ejecuta la Auditoría de seguridad para añadir hallazgos de secretos (SEC-*) y de configuración de agentes (AGENT-*).",
    dom_code:"Arquitectura del código",dom_quality:"Calidad del análisis",dom_security:"Secretos",dom_agent:"Configuración de agentes",dom_binary:"Binarios y archivos",dom_network:"Red",
    sev_critical:"Crítica",sev_high:"Alta",sev_medium:"Media",sev_low:"Baja",sev_info:"Info",
    ctxTitle:"Contexto de tarea",ctxSub:"Describe una tarea y obtén los archivos a leer, en orden, dentro de un presupuesto de tokens.",ctxPlaceholder:"p. ej. corregir el reintento con backoff del webhook de pagos",ctxBudget:"Presupuesto de tokens",ctxRun:"Buscar archivos",ctxRunning:"Clasificando…",ctxEmpty:"Ningún archivo coincide. Usa nombres de funciones, clases o archivos.",ctxSummary:"{n} archivos · ~{used} de {budget} tokens",ctxMatch:"coincidencia",ctxNeighbor:"vecino",ctxTokens:"tokens",ctxDependents:"dependientes",ctxHighlightAll:"Resaltar en el grafo",ctxHowItWorks:"Clasificado con BM25 sobre identificadores del código. Los archivos 'vecinos' no mencionan la tarea, pero importan o son importados por una coincidencia. Ctrl+Enter ejecuta la búsqueda.",
    rvTitle:"Inspeccionar archivos",rvSub:"Ingeniería inversa estática de cualquier archivo o carpeta del proyecto: binarios, comprimidos, bases de datos, datos. No se ejecuta nada.",rvPathPlaceholder:"Ruta dentro del proyecto (p. ej. bin/app o .)",rvRun:"Inspeccionar",rvRunning:"Inspeccionando…",rvStrings:"Extraer cadenas",rvHint:"Introduce la ruta de un archivo, o '.' para inventariar el proyecto y ver qué binarios cargan qué bibliotecas.",rvType:"Tipo",rvSize:"Tamaño",rvSha256:"SHA-256",rvEntropy:"Entropía",rvHardening:"Mitigaciones",rvLibraries:"Bibliotecas",rvData:"Resumen de datos",rvFindings:"Hallazgos",rvNoFindings:"Sin hallazgos.",rvOpenInspector:"Abrir hexdump y cadenas",rvLimitations:"Limitaciones",rvBinaries:"Binarios y contenedores",rvInventory:"{files} archivos · {size}",rvMostLinked:"Bibliotecas más enlazadas",rvLinkage:"Grafo de bibliotecas",rvLinkageExplain:"Binarios (azul) y las bibliotecas que cargan (verde). Haz clic en un binario para inspeccionarlo.",
    inspectorTab:"Inspector",hxTitle:"Hexdump",hxOffset:"Offset",hxGo:"Ir",hxPrev:"◀ Anterior",hxNext:"Siguiente ▶",hxEnd:"Final",stTitle:"Cadenas",stFilter:"Filtrar cadenas…",stInteresting:"Solo relevantes",stNone:"No hay cadenas para mostrar.",entTitle:"Perfil de entropía",entExplain:"Bits por byte a lo largo del archivo (haz clic en una barra para llevar el hexdump allí). Cerca de 8 = comprimido o cifrado; cerca de 0 = relleno.",
    auTitle:"Auditoría de seguridad",auSub:"Secretos confirmados y configuración arriesgada de agentes de IA: servidores MCP, permisos, hooks, Unicode oculto. Sin conexión; los secretos siempre se ocultan.",auRun:"Ejecutar auditoría",auRunning:"Auditando…",auSecrets:"Secretos",auCode:"Código",auAgent:"Config. de agentes",auFiles:"{n} archivos de texto analizados",auGitAware:"tiene en cuenta git",auNotGit:"no es un repositorio git",auClean:"No se encontraron secretos ni configuración arriesgada de agentes.",auNotes:"Notas",auHint:"Ejecuta la auditoría para buscar secretos y riesgos de configuración de agentes de IA en este proyecto.",
  },
  fr: {
    navFindings:"Constats",navContext:"Contexte de tâche",navInspect:"Inspecter des fichiers",navAudit:"Audit de sécurité",
    tkError:"Erreur",tkUnavailable:"Ce serveur ne prend pas en charge cette fonction. Utilisez `archmap serve` d'ArchMAP 1.4.0 ou plus.",tkNotLocal:"Disponible uniquement lorsque l'interface est ouverte depuis localhost.",
    qualTitle:"Fiabilité de l'analyse",qualExplain:"Part du projet présente dans le graphe. En dessous de 'élevée', « aucun dépendant » et les petits rayons d'impact sont des bornes inférieures.",qualParsed:"Fichiers analysés",qualResolution:"Résolution des imports",qualFailures:"Échecs d'analyse",qualSkipped:"Ignorés (encodage/taille)",qualByLang:"Langage",qualFiles:"Fichiers",qualNoWarnings:"Aucune lacune : tous les fichiers source trouvés ont été analysés.",qualLevel_high:"Élevée",qualLevel_medium:"Moyenne",qualLevel_low:"Faible",kpiConfidence:"Fiabilité",
    findingsTitle:"Constats",findingsSub:"Chaque problème détecté, avec ID stable, sévérité, confiance et preuves.",fDomain:"Domaine",fAllDomains:"Tous les domaines",fMinSeverity:"Sévérité minimale",fAll:"Toutes",fNone:"Aucun constat ne correspond à ces filtres.",fEvidence:"Preuves",fConfidence:"Confiance",fShowInGraph:"Voir dans le graphe",fAuditHint:"Lancez l'Audit de sécurité pour ajouter les constats de secrets (SEC-*) et de configuration d'agents (AGENT-*).",
    dom_code:"Architecture du code",dom_quality:"Qualité de l'analyse",dom_security:"Secrets",dom_agent:"Configuration des agents",dom_binary:"Binaires et fichiers",dom_network:"Réseau",
    sev_critical:"Critique",sev_high:"Élevée",sev_medium:"Moyenne",sev_low:"Faible",sev_info:"Info",
    ctxTitle:"Contexte de tâche",ctxSub:"Décrivez une tâche et obtenez les fichiers à lire, dans l'ordre, dans un budget de tokens.",ctxPlaceholder:"ex. corriger le retry avec backoff du webhook de paiement",ctxBudget:"Budget de tokens",ctxRun:"Trouver les fichiers",ctxRunning:"Classement…",ctxEmpty:"Aucun fichier trouvé. Utilisez des noms de fonctions, classes ou fichiers.",ctxSummary:"{n} fichiers · ~{used} sur {budget} tokens",ctxMatch:"correspondance",ctxNeighbor:"voisin",ctxTokens:"tokens",ctxDependents:"dépendants",ctxHighlightAll:"Surligner dans le graphe",ctxHowItWorks:"Classé avec BM25 sur les identifiants du code. Les fichiers « voisins » ne citent pas la tâche mais importent une correspondance ou sont importés par elle. Ctrl+Entrée lance la recherche.",
    rvTitle:"Inspecter des fichiers",rvSub:"Rétro-ingénierie statique de tout fichier ou dossier du projet : binaires, archives, bases de données, données. Rien n'est exécuté.",rvPathPlaceholder:"Chemin dans le projet (ex. bin/app ou .)",rvRun:"Inspecter",rvRunning:"Inspection…",rvStrings:"Extraire les chaînes",rvHint:"Saisissez un chemin de fichier, ou '.' pour inventorier le projet et voir quels binaires chargent quelles bibliothèques.",rvType:"Type",rvSize:"Taille",rvSha256:"SHA-256",rvEntropy:"Entropie",rvHardening:"Protections",rvLibraries:"Bibliothèques",rvData:"Résumé des données",rvFindings:"Constats",rvNoFindings:"Aucun constat.",rvOpenInspector:"Ouvrir hexdump et chaînes",rvLimitations:"Limites",rvBinaries:"Binaires et conteneurs",rvInventory:"{files} fichiers · {size}",rvMostLinked:"Bibliothèques les plus liées",rvLinkage:"Graphe des bibliothèques",rvLinkageExplain:"Binaires (bleu) et bibliothèques qu'ils chargent (vert). Cliquez sur un binaire pour l'inspecter.",
    inspectorTab:"Inspecteur",hxTitle:"Hexdump",hxOffset:"Offset",hxGo:"Aller",hxPrev:"◀ Préc.",hxNext:"Suiv. ▶",hxEnd:"Fin",stTitle:"Chaînes",stFilter:"Filtrer les chaînes…",stInteresting:"Pertinentes seulement",stNone:"Aucune chaîne à afficher.",entTitle:"Profil d'entropie",entExplain:"Bits par octet le long du fichier (cliquez sur une barre pour y placer l'hexdump). Proche de 8 = compressé ou chiffré ; proche de 0 = remplissage.",
    auTitle:"Audit de sécurité",auSub:"Secrets commités et configuration risquée des agents IA : serveurs MCP, permissions, hooks, Unicode invisible. Hors ligne ; les secrets sont toujours masqués.",auRun:"Lancer l'audit",auRunning:"Audit en cours…",auSecrets:"Secrets",auCode:"Code",auAgent:"Config. des agents",auFiles:"{n} fichiers texte analysés",auGitAware:"tient compte de git",auNotGit:"pas un dépôt git",auClean:"Aucun secret ni configuration d'agent risquée trouvé.",auNotes:"Notes",auHint:"Lancez l'audit pour rechercher les secrets et les risques de configuration des agents IA dans ce projet.",
  },
  de: {
    navFindings:"Befunde",navContext:"Aufgabenkontext",navInspect:"Dateien untersuchen",navAudit:"Sicherheitsaudit",
    tkError:"Fehler",tkUnavailable:"Dieser Server unterstützt diese Funktion nicht. Nutze `archmap serve` aus ArchMAP 1.4.0 oder neuer.",tkNotLocal:"Nur verfügbar, wenn die Oberfläche über localhost geöffnet wird.",
    qualTitle:"Analyse-Zuverlässigkeit",qualExplain:"Wie viel des Projekts im Graphen gelandet ist. Unter 'hoch' sind „keine Abhängigen“ und kleine Auswirkungsradien Untergrenzen.",qualParsed:"Geparste Dateien",qualResolution:"Import-Auflösung",qualFailures:"Parse-Fehler",qualSkipped:"Übersprungen (Kodierung/Größe)",qualByLang:"Sprache",qualFiles:"Dateien",qualNoWarnings:"Keine Lücken: Jede gefundene Quelldatei wurde geparst.",qualLevel_high:"Hoch",qualLevel_medium:"Mittel",qualLevel_low:"Niedrig",kpiConfidence:"Zuverlässigkeit",
    findingsTitle:"Befunde",findingsSub:"Jedes gefundene Problem mit stabiler ID, Schweregrad, Konfidenz und Belegen.",fDomain:"Bereich",fAllDomains:"Alle Bereiche",fMinSeverity:"Mindestschweregrad",fAll:"Alle",fNone:"Keine Befunde für diese Filter.",fEvidence:"Belege",fConfidence:"Konfidenz",fShowInGraph:"Im Graphen zeigen",fAuditHint:"Starte das Sicherheitsaudit, um Befunde zu Geheimnissen (SEC-*) und Agent-Konfiguration (AGENT-*) hinzuzufügen.",
    dom_code:"Code-Architektur",dom_quality:"Analysequalität",dom_security:"Geheimnisse",dom_agent:"Agent-Konfiguration",dom_binary:"Binärdateien & Dateien",dom_network:"Netzwerk",
    sev_critical:"Kritisch",sev_high:"Hoch",sev_medium:"Mittel",sev_low:"Niedrig",sev_info:"Info",
    ctxTitle:"Aufgabenkontext",ctxSub:"Beschreibe eine Aufgabe und erhalte die zu lesenden Dateien in Reihenfolge innerhalb eines Token-Budgets.",ctxPlaceholder:"z. B. Retry-Backoff im Zahlungs-Webhook korrigieren",ctxBudget:"Token-Budget",ctxRun:"Dateien finden",ctxRunning:"Wird bewertet…",ctxEmpty:"Keine Datei gefunden. Nutze Namen von Funktionen, Klassen oder Dateien.",ctxSummary:"{n} Dateien · ~{used} von {budget} Tokens",ctxMatch:"Treffer",ctxNeighbor:"Nachbar",ctxTokens:"Tokens",ctxDependents:"Abhängige",ctxHighlightAll:"Im Graphen hervorheben",ctxHowItWorks:"Mit BM25 über Code-Bezeichner gerankt. „Nachbar“-Dateien erwähnen die Aufgabe nicht, importieren aber einen Treffer oder werden von ihm importiert. Strg+Enter startet die Suche.",
    rvTitle:"Dateien untersuchen",rvSub:"Statisches Reverse Engineering jeder Datei oder jedes Ordners im Projekt: Binärdateien, Archive, Datenbanken, Daten. Nichts wird ausgeführt.",rvPathPlaceholder:"Pfad im Projekt (z. B. bin/app oder .)",rvRun:"Untersuchen",rvRunning:"Wird untersucht…",rvStrings:"Strings extrahieren",rvHint:"Gib einen Dateipfad ein, oder '.', um das Projekt zu inventarisieren und zu sehen, welche Binärdateien welche Bibliotheken laden.",rvType:"Typ",rvSize:"Größe",rvSha256:"SHA-256",rvEntropy:"Entropie",rvHardening:"Schutzmaßnahmen",rvLibraries:"Bibliotheken",rvData:"Datenübersicht",rvFindings:"Befunde",rvNoFindings:"Keine Befunde.",rvOpenInspector:"Hexdump & Strings öffnen",rvLimitations:"Einschränkungen",rvBinaries:"Binärdateien & Container",rvInventory:"{files} Dateien · {size}",rvMostLinked:"Meistgenutzte Bibliotheken",rvLinkage:"Bibliotheksgraph",rvLinkageExplain:"Binärdateien (blau) und die geladenen Bibliotheken (grün). Klicke auf eine Binärdatei, um sie zu untersuchen.",
    inspectorTab:"Inspektor",hxTitle:"Hexdump",hxOffset:"Offset",hxGo:"Los",hxPrev:"◀ Zurück",hxNext:"Weiter ▶",hxEnd:"Ende",stTitle:"Strings",stFilter:"Strings filtern…",stInteresting:"Nur relevante",stNone:"Keine Strings anzuzeigen.",entTitle:"Entropieprofil",entExplain:"Bits pro Byte entlang der Datei (Balken anklicken, um den Hexdump dorthin zu bewegen). Nahe 8 = komprimiert oder verschlüsselt; nahe 0 = Auffüllung.",
    auTitle:"Sicherheitsaudit",auSub:"Eingecheckte Geheimnisse und riskante KI-Agent-Konfiguration: MCP-Server, Berechtigungen, Hooks, unsichtbares Unicode. Offline; Geheimnisse werden immer maskiert.",auRun:"Audit starten",auRunning:"Audit läuft…",auSecrets:"Geheimnisse",auCode:"Code",auAgent:"Agent-Konfig.",auFiles:"{n} Textdateien geprüft",auGitAware:"git-bewusst",auNotGit:"kein Git-Repository",auClean:"Keine Geheimnisse oder riskante Agent-Konfiguration gefunden.",auNotes:"Hinweise",auHint:"Starte das Audit, um dieses Projekt nach Geheimnissen und KI-Agent-Konfigurationsrisiken zu durchsuchen.",
  },
  zh: {
    navFindings:"问题清单",navContext:"任务上下文",navInspect:"检查文件",navAudit:"安全审计",
    tkError:"错误",tkUnavailable:"此服务器不支持该功能。请使用 ArchMAP 1.4.0 或更高版本的 `archmap serve`。",tkNotLocal:"仅在通过 localhost 打开界面时可用。",
    qualTitle:"分析可信度",qualExplain:"项目有多少进入了依赖图。低于“高”时，“无依赖方”和较小的影响范围只是下限。",qualParsed:"已解析文件",qualResolution:"导入解析率",qualFailures:"解析失败",qualSkipped:"已跳过（编码/大小）",qualByLang:"语言",qualFiles:"文件",qualNoWarnings:"无缺口：发现的所有源文件均已解析。",qualLevel_high:"高",qualLevel_medium:"中",qualLevel_low:"低",kpiConfidence:"可信度",
    findingsTitle:"问题清单",findingsSub:"发现的每个问题，含稳定 ID、严重程度、置信度和证据。",fDomain:"领域",fAllDomains:"所有领域",fMinSeverity:"最低严重程度",fAll:"全部",fNone:"没有符合筛选条件的问题。",fEvidence:"证据",fConfidence:"置信度",fShowInGraph:"在图中显示",fAuditHint:"运行安全审计，以在此加入密钥（SEC-*）和智能体配置（AGENT-*）问题。",
    dom_code:"代码架构",dom_quality:"分析质量",dom_security:"密钥",dom_agent:"智能体配置",dom_binary:"二进制与文件",dom_network:"网络",
    sev_critical:"严重",sev_high:"高",sev_medium:"中",sev_low:"低",sev_info:"信息",
    ctxTitle:"任务上下文",ctxSub:"描述任务，按顺序获得在 token 预算内需要阅读的文件。",ctxPlaceholder:"例如：修复支付 webhook 的重试退避",ctxBudget:"Token 预算",ctxRun:"查找文件",ctxRunning:"排序中…",ctxEmpty:"没有匹配的文件。请使用函数、类或文件名。",ctxSummary:"{n} 个文件 · 约 {used}/{budget} tokens",ctxMatch:"匹配",ctxNeighbor:"邻近",ctxTokens:"tokens",ctxDependents:"依赖方",ctxHighlightAll:"在图中高亮",ctxHowItWorks:"基于代码标识符的 BM25 排序。“邻近”文件未提及任务，但导入了匹配文件或被其导入。Ctrl+Enter 执行搜索。",
    rvTitle:"检查文件",rvSub:"对项目中任意文件或目录做静态逆向分析：二进制、压缩包、数据库、数据。不执行任何内容。",rvPathPlaceholder:"项目内路径（例如 bin/app 或 .）",rvRun:"检查",rvRunning:"检查中…",rvStrings:"提取字符串",rvHint:"输入文件路径，或输入 '.' 盘点整个项目并查看哪些二进制加载了哪些库。",rvType:"类型",rvSize:"大小",rvSha256:"SHA-256",rvEntropy:"熵",rvHardening:"安全缓解",rvLibraries:"库",rvData:"数据摘要",rvFindings:"问题",rvNoFindings:"没有问题。",rvOpenInspector:"打开十六进制与字符串",rvLimitations:"局限",rvBinaries:"二进制与容器",rvInventory:"{files} 个文件 · {size}",rvMostLinked:"最常链接的库",rvLinkage:"库链接图",rvLinkageExplain:"二进制（蓝色）及其加载的库（绿色）。点击二进制进行检查。",
    inspectorTab:"检查器",hxTitle:"十六进制",hxOffset:"偏移",hxGo:"跳转",hxPrev:"◀ 上一页",hxNext:"下一页 ▶",hxEnd:"末尾",stTitle:"字符串",stFilter:"筛选字符串…",stInteresting:"仅显示重要的",stNone:"没有可显示的字符串。",entTitle:"熵分布",entExplain:"文件各处每字节的比特数（点击柱条将十六进制视图跳转到该处）。接近 8 = 压缩或加密；接近 0 = 填充。",
    auTitle:"安全审计",auSub:"已提交的密钥与有风险的 AI 智能体配置：MCP 服务器、权限、钩子、隐藏 Unicode。离线运行；密钥值始终打码。",auRun:"运行审计",auRunning:"审计中…",auSecrets:"密钥",auCode:"代码",auAgent:"智能体配置",auFiles:"已扫描 {n} 个文本文件",auGitAware:"结合 git 状态",auNotGit:"不是 git 仓库",auClean:"未发现密钥或有风险的智能体配置。",auNotes:"说明",auHint:"运行审计，扫描本项目中的密钥和 AI 智能体配置风险。",
  },
};
