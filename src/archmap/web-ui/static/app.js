const FILE_COLOR   = "#6173e0";
const PKG_COLOR    = "#62b386";
const CYCLE_COLOR  = "#d35266";
const EDGE_COLOR   = "#c4cad5";
const TRACE_COLORS = ["#5667d8", "#7e8de6", "#a8b0ee", "#c8cef4", "#dde0f8"];

const state = { folder: "all", cyclesOnly: false, search: "", heatmap: false };

const el = {
  graph:         document.getElementById("graph"),
  folderFilter:  document.getElementById("folderFilter"),
  cyclesOnly:    document.getElementById("cyclesOnly"),
  heatmapMode:   document.getElementById("heatmapMode"),
  heatmapLegend: document.getElementById("heatmapLegend"),
  searchInput:   document.getElementById("searchInput"),
  zoomInBtn:     document.getElementById("zoomInBtn"),
  zoomOutBtn:    document.getElementById("zoomOutBtn"),
  fitBtn:        document.getElementById("fitBtn"),
  layoutBtn:     document.getElementById("layoutBtn"),
  resetBtn:      document.getElementById("resetBtn"),
  summary:       document.getElementById("summary"),
  criticalList:  document.getElementById("criticalList"),
  cyclesList:    document.getElementById("cyclesList"),
  selectionInfo: document.getElementById("selectionInfo"),
  themeToggle:   document.getElementById("themeToggle"),
  refreshBtn:    document.getElementById("refreshBtn"),
  risksSummary:  document.getElementById("risksSummary"),
  openProjectBtn:document.getElementById("openProjectBtn"),
};

let cy = null;
let cyLayers = null;
let controlsBound = false;
let reportData = null;

const savedTheme = localStorage.getItem("archmap-theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);

init().catch((err) => {
  el.selectionInfo.innerHTML = `<p class="selection-muted">Failed to load: ${escHtml(err.message)}</p>`;
});

async function init() {
  el.refreshBtn?.classList.add("loading");
  try {
    const res = await fetch("/api/graph");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();
    reportData = report;
    fillSidebar(report);
    if (cy) { cy.destroy(); cy = null; }
    initGraph(report);
    if (!controlsBound) { bindControls(); controlsBound = true; }
    updateStatusBar(report);
    updateProjectHeader(report);
  } finally {
    el.refreshBtn?.classList.remove("loading");
  }
}

/* ============================================================
   Sidebar
   ============================================================ */

function fillSidebar(report) {
  renderHealth(report.metrics);
  renderSummary(report.metrics);
  renderRisks(report);
  renderCriticalFiles(report.metrics.criticalFiles);
  renderCycles(report.cycles);
  populateFolderFilter(report.nodes);
}

function updateProjectHeader(report) {
  const root = report.projectRoot ?? "";
  const parts = root.replace(/\\/g, "/").split("/");
  const name = parts[parts.length - 1] || root;

  const pathEl = document.getElementById("projectPath");
  const breadEl = document.getElementById("breadcrumbProject");
  if (pathEl) pathEl.textContent = root || "Unknown";
  if (breadEl) breadEl.textContent = name || "project";
}

function updateStatusBar(report) {
  const nodes = (report.nodes ?? []).length;
  const edges = (report.edges ?? []).length;
  const cycles = (report.cycles ?? []).length;
  const el = document.getElementById("statusCounts");
  if (el) {
    el.innerHTML = `<span class="mono">${nodes}</span> nodes · <span class="mono">${edges}</span> edges · <span class="mono">${cycles}</span> cycles`;
  }
}

/* ── Health gauge ── */
function renderHealth(metrics) {
  const score = Math.round(metrics.architectureHealthScore ?? 100);
  const circumference = 97.4;
  const offset = circumference * (1 - score / 100);

  const gaugeBar = document.querySelector(".gauge-bar");
  const gaugeLabel = document.getElementById("gaugeLabel");
  const healthPill = document.getElementById("healthPill");
  const statusEl = document.getElementById("healthStatus");
  const descEl = document.getElementById("healthDesc");

  if (gaugeBar) {
    gaugeBar.setAttribute("stroke-dashoffset", offset.toFixed(1));
    gaugeBar.style.stroke = score >= 80 ? "var(--ok)" : score >= 60 ? "var(--warn)" : "var(--danger)";
  }
  if (gaugeLabel) gaugeLabel.textContent = score;
  if (healthPill) healthPill.textContent = score;

  let statusText, descText, pulseColor, pulseShadow;
  if (score >= 80) {
    statusText = "Healthy"; descText = "Architecture is in good shape.";
    pulseColor = "var(--ok)"; pulseShadow = "0 0 0 4px oklch(0.66 0.14 150/0.18)";
  } else if (score >= 60) {
    statusText = "Attention needed";
    descText = `${metrics.circularDependencyCount ?? 0} cycles and ${metrics.architectureRuleViolations ?? 0} rule violations detected.`;
    pulseColor = "var(--warn)"; pulseShadow = "0 0 0 4px oklch(0.76 0.14 80/0.18)";
  } else {
    statusText = "Critical issues";
    descText = "Multiple architectural problems require immediate attention.";
    pulseColor = "var(--danger)"; pulseShadow = "0 0 0 4px oklch(0.62 0.18 25/0.18)";
  }

  if (statusEl) {
    statusEl.innerHTML = `<span class="pulse" style="background:${pulseColor};box-shadow:${pulseShadow}"></span>${statusText}`;
  }
  if (descEl) descEl.textContent = descText;

  renderBarRows(metrics);
}

function renderBarRows(metrics) {
  const cycles = metrics.circularDependencyCount ?? 0;
  const viols = metrics.architectureRuleViolations ?? 0;
  const gods = (metrics.criticalFiles ?? []).filter(f => f.dependents > 8).length;
  const avgRaw = metrics.complexity?.avgComplexityScore ?? 0;
  const avg = (avgRaw * 100).toFixed(1);

  const setBar = (id, valId, value, max, cls) => {
    const bar = document.getElementById(id);
    const valEl = document.getElementById(valId);
    if (bar) { bar.style.width = Math.min(100, (value / max) * 100) + "%"; bar.className = `bar-fill ${cls}`; }
    if (valEl) valEl.textContent = value;
  };

  setBar("barCycles",  "valCycles",  cycles, 10,  cycles > 0 ? "warn" : "ok");
  setBar("barViols",   "valViols",   viols,  10,  viols > 0 ? "warn" : "ok");
  setBar("barGods",    "valGods",    gods,   10,  gods > 2 ? "warn" : "ok");
  setBar("barComplex", "valComplex", avg,    100, parseFloat(avg) > 50 ? "warn" : "ok");
}

/* ── Summary KPIs ── */
function renderSummary(metrics) {
  if (!el.summary) return;
  const kpis = [
    { label: "Files",        value: metrics.filesAnalyzed,           accent: true },
    { label: "Dependencies", value: metrics.totalDependencies },
    { label: "External pkg", value: metrics.externalDependencies },
    { label: "Cycles",       value: metrics.circularDependencyCount },
  ];
  el.summary.innerHTML = kpis.map((k, i) => `
    <div class="kpi${k.accent ? " kpi--accent" : ""}">
      <span class="kpi-label">${k.label}</span>
      <span class="kpi-value">${k.value ?? 0}</span>
    </div>`).join("");
}

/* ── Critical files ── */
function renderCriticalFiles(criticalFiles) {
  const list = el.criticalList;
  list.innerHTML = "";
  const top = (criticalFiles ?? []).slice(0, 10);

  const pill = document.getElementById("criticalPill");
  if (pill) pill.textContent = top.length;

  if (top.length === 0) {
    list.innerHTML = `<li class="list-item"><span style="color:var(--muted);font-size:12px">No critical files detected.</span></li>`;
    return;
  }

  top.forEach((file, i) => {
    const dep = file.dependents ?? 0;
    const cls = dep > 8 ? "danger" : dep > 5 ? "warn" : "";
    const folder = file.file.replace(/\\/g, "/").split("/").slice(0, -1).join("/") || "—";
    const li = document.createElement("li");
    li.className = "list-item";
    li.innerHTML = `
      <span class="list-rank">${i + 1}</span>
      <div class="list-main">
        <span class="list-name">${escHtml(file.file)}</span>
        <span class="list-meta">${escHtml(folder)}</span>
      </div>
      <span class="list-stat${cls ? " " + cls : ""}">${dep}</span>`;
    list.appendChild(li);
  });
}

/* ── Cycles ── */
function renderCycles(cycles) {
  const list = el.cyclesList;
  list.innerHTML = "";
  const pill = document.getElementById("cyclesPill");
  if (pill) pill.textContent = (cycles ?? []).length;

  if (!cycles || cycles.length === 0) {
    list.innerHTML = `<li style="padding:14px;color:var(--muted);font-size:12px;text-align:center">No circular dependencies found.</li>`;
    return;
  }

  cycles.slice(0, 12).forEach((cycle, i) => {
    const steps = [...cycle, cycle[0]];
    const short = steps.map(s => s.replace(/\\/g, "/").split("/").pop() || s);
    const li = document.createElement("li");
    li.className = "cycle-item";
    li.innerHTML = `<div class="cy-label">Cycle #${i + 1} · ${cycle.length} hops</div>` +
      short.map((s, si) => si < short.length - 1
        ? `<span>${escHtml(s)}</span><span class="cy-arrow">→</span>`
        : `<span>${escHtml(s)}</span>`
      ).join("");
    list.appendChild(li);
  });
}

/* ── Risks ── */
function renderRisks(report) {
  const container = el.risksSummary;
  container.innerHTML = "";
  const risks = [];

  if ((report.cycles ?? []).length > 0) {
    risks.push({ level: "high", badge: "!", msg: `${report.cycles.length} circular dependencies detected`, tip: "Refactor using interfaces or events to break the cycles." });
  }
  const godFiles = (report.metrics.criticalFiles ?? []).filter(f => f.dependents > 8);
  if (godFiles.length > 0) {
    risks.push({ level: "medium", badge: "·", msg: `${godFiles.length} hub file${godFiles.length > 1 ? "s" : ""} with many dependents`, tip: "Consider splitting these into smaller modules." });
  }

  const pill = document.getElementById("risksPill");
  if (pill) pill.textContent = risks.length || "0";

  if (risks.length === 0) {
    container.innerHTML = `<div class="empty-state"><span>No architectural risks detected.</span></div>`;
    return;
  }

  for (const risk of risks) {
    const div = document.createElement("div");
    div.className = `risk-item risk-${risk.level}`;
    div.innerHTML = `
      <div class="risk-badge">${risk.badge}</div>
      <div class="risk-body">
        <p class="risk-msg">${escHtml(risk.msg)}</p>
        <p class="risk-tip">${escHtml(risk.tip)}</p>
      </div>`;
    container.appendChild(div);
  }
}

/* ── Folder filter ── */
function populateFolderFilter(nodes) {
  const folders = new Set(
    (nodes ?? []).filter(n => n.type === "file").map(n => n.folder).filter(Boolean)
  );
  el.folderFilter.innerHTML = "";
  for (const val of ["all", ...[...folders].sort()]) {
    const opt = document.createElement("option");
    opt.value = val;
    opt.textContent = val === "all" ? "All folders" : val;
    el.folderFilter.appendChild(opt);
  }
}

/* ============================================================
   Graph
   ============================================================ */

function initGraph(report) {
  const elements = [
    ...report.nodes.map(n => ({
      data: {
        id: n.id, label: n.label, type: n.type,
        folder: n.folder, language: n.language,
        isCircular: Boolean(n.isCircular),
        outgoing: n.outgoing ?? 0, incoming: n.incoming ?? 0,
        complexityImports: n.complexityImports ?? 0,
        complexityScore: n.complexityScore ?? 0,
        heatColor: heatColor(n.complexityScore ?? 0),
      },
    })),
    ...report.edges.map(e => ({
      data: { id: e.id, source: e.source, target: e.target, isCircular: Boolean(e.isCircular) },
    })),
  ];

  cy = cytoscape({
    container: el.graph,
    elements,
    wheelSensitivity: 0.2,
    style: buildStylesheet(),
    layout: {
      name: "cose",
      animate: true, fit: true, padding: 60,
      idealEdgeLength: 110, nodeOverlap: 14,
      nodeRepulsion: 9000, gravity: 0.6,
    },
  });

  cy.on("tap", "node", (e) => {
    highlightNode(e.target);
    renderSelection(e.target);
  });
  cy.on("tap", (e) => {
    if (e.target === cy) {
      cy.elements().removeClass("selected dimmed highlighted");
      el.selectionInfo.innerHTML = `<p class="selection-muted">${escHtml(t("selectionHint"))}</p>`;
    }
  });
  cy.on("zoom", () => {
    const pct = Math.round(cy.zoom() * 100) + "%";
    const z1 = document.getElementById("zoomReadout");
    const z2 = document.getElementById("zoomPct");
    if (z1) z1.textContent = pct;
    if (z2) z2.textContent = pct;
  });
}

function buildStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "font-family": "Inter, sans-serif",
        "font-size": 10.5,
        "font-weight": 500,
        "text-valign": "bottom",
        "text-margin-y": 6,
        "text-wrap": "wrap",
        "text-max-width": 110,
        color: "#2a3344",
        "border-color": "rgba(255,255,255,0.85)",
        "border-width": 1.5,
        "background-color": FILE_COLOR,
      },
    },
    {
      selector: 'node[type = "file"]',
      style: { shape: "round-rectangle", width: 38, height: 22, "background-color": FILE_COLOR },
    },
    {
      selector: 'node[type = "package"]',
      style: { shape: "diamond", width: 22, height: 22, "background-color": PKG_COLOR },
    },
    {
      selector: "edge",
      style: {
        width: 1.1,
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "target-arrow-color": EDGE_COLOR,
        "line-color": EDGE_COLOR,
        "arrow-scale": 0.85,
        opacity: 0.85,
      },
    },
    {
      selector: "edge[?isCircular]",
      style: { "line-color": CYCLE_COLOR, "target-arrow-color": CYCLE_COLOR, width: 1.6, opacity: 1 },
    },
    {
      selector: "node[?isCircular]",
      style: { "border-color": CYCLE_COLOR, "border-width": 2.5 },
    },
    { selector: ".selected",    style: { "border-color": "#5667d8", "border-width": 3 } },
    { selector: ".highlighted", style: { opacity: 1 } },
    { selector: ".dimmed",      style: { opacity: 0.12 } },
    { selector: ".hidden",      style: { display: "none" } },
  ];
}

/* ============================================================
   Controls
   ============================================================ */

function bindControls() {
  el.folderFilter.addEventListener("change", () => { state.folder = el.folderFilter.value; applyFilters(); });
  el.cyclesOnly.addEventListener("change", () => { state.cyclesOnly = el.cyclesOnly.checked; applyFilters(); });
  el.heatmapMode.addEventListener("change", () => { state.heatmap = el.heatmapMode.checked; applyHeatmap(); });
  el.searchInput.addEventListener("input", () => { state.search = el.searchInput.value.trim().toLowerCase(); applyFilters(); });

  el.zoomInBtn.addEventListener("click", () => cy.zoom({ level: cy.zoom() * 1.2, renderedPosition: { x: el.graph.clientWidth / 2, y: el.graph.clientHeight / 2 } }));
  el.zoomOutBtn.addEventListener("click", () => cy.zoom({ level: cy.zoom() / 1.2, renderedPosition: { x: el.graph.clientWidth / 2, y: el.graph.clientHeight / 2 } }));
  el.fitBtn.addEventListener("click", () => cy.fit(cy.elements(":visible"), 60));
  el.layoutBtn.addEventListener("click", () => {
    let uiCfg = { layout: "cose" };
    try { uiCfg = { ...uiCfg, ...(JSON.parse(localStorage.getItem("archmap.config.ui")) ?? {}) }; } catch (_) {}
    cy.layout({ name: uiCfg.layout, animate: !document.body.classList.contains("no-animations"), fit: true, padding: 60, idealEdgeLength: 110, nodeRepulsion: 9000 }).run();
  });
  el.resetBtn.addEventListener("click", () => {
    cy.elements().removeClass("selected dimmed highlighted");
    el.selectionInfo.innerHTML = `<p class="selection-muted">Click a node to inspect dependencies.</p>`;
  });

  el.themeToggle.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("archmap-theme", next);
  });

  el.refreshBtn.addEventListener("click", async () => {
    try { await fetch("/api/reanalyze", { method: "POST" }); } catch { /* ignored */ }
    await init();
  });

  el.openProjectBtn.addEventListener("click", async () => {
    el.openProjectBtn.classList.add("loading");
    try {
      const res = await fetch("/api/open", { method: "POST" });
      if (res.status === 200) await init();
    } catch { /* ignored */ }
    finally { el.openProjectBtn.classList.remove("loading"); }
  });

  // Nav rail — left panel view switching
  document.getElementById("exportBtn")?.addEventListener("click", exportGraphPng);
  document.getElementById("exportSvgBtn")?.addEventListener("click", exportGraphSvg);

  document.getElementById("navBtnGraph")?.addEventListener("click",    () => switchLeftView("graph"));
  document.getElementById("navBtnInsights")?.addEventListener("click", () => switchLeftView("insights"));
  document.getElementById("navBtnRules")?.addEventListener("click",    () => switchLeftView("rules"));
  document.getElementById("navBtnTrace")?.addEventListener("click",    () => switchLeftView("trace"));
  document.getElementById("navBtnAdvisor")?.addEventListener("click",  () => switchLeftView("advisor"));
  document.getElementById("navBtnConfig")?.addEventListener("click",   () => switchLeftView("config"));
  const _railLogo = document.getElementById("railLogo");
  _railLogo?.addEventListener("click", () => switchLeftView("graph"));
  _railLogo?.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") switchLeftView("graph"); });

  // Trace panel controls
  document.getElementById("traceRunBtn")?.addEventListener("click", () => {
    const input = document.getElementById("traceInput");
    if (input?.value.trim()) traceFromQuery(input.value.trim());
  });
  document.getElementById("traceInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const v = e.target.value.trim();
      if (v) traceFromQuery(v);
    }
  });

  // Canvas tab switching
  document.getElementById("canvasTabGraph")?.addEventListener("click",   () => switchCanvasTab("graph"));
  document.getElementById("canvasTabLayers")?.addEventListener("click",  () => switchCanvasTab("layers"));
  document.getElementById("canvasTabMatrix")?.addEventListener("click",  () => switchCanvasTab("matrix"));
}

/* ============================================================
   Filters & highlight
   ============================================================ */

function applyFilters() {
  const visible = new Set();

  cy.nodes().forEach(node => {
    let show = true;
    if (node.data("type") === "file") {
      if (state.folder !== "all" && node.data("folder") !== state.folder) show = false;
      if (state.cyclesOnly && !node.data("isCircular")) show = false;
    } else {
      show = !state.cyclesOnly;
    }
    if (show && state.search) {
      show = String(node.data("label") ?? "").toLowerCase().includes(state.search);
    }
    node.scratch("_vis", show);
  });

  if (!state.cyclesOnly) {
    cy.nodes('[type = "package"]').forEach(n => {
      const connected = n.connectedEdges().some(e => e.source().scratch("_vis") && e.target().scratch("_vis"));
      n.scratch("_vis", connected);
    });
  }

  cy.nodes().forEach(n => { const v = Boolean(n.scratch("_vis")); n.toggleClass("hidden", !v); if (v) visible.add(n.id()); });
  cy.edges().forEach(e => {
    const v = visible.has(e.source().id()) && visible.has(e.target().id()) && !(state.cyclesOnly && !e.data("isCircular"));
    e.toggleClass("hidden", !v);
  });

  cy.elements().removeClass("selected dimmed highlighted");
  applyHeatmap();
  cy.fit(cy.elements(":visible"), 60);
}

function applyHeatmap() {
  cy.nodes('[type = "file"]').forEach(n => n.style("background-color", state.heatmap ? n.data("heatColor") : FILE_COLOR));
  cy.nodes('[type = "package"]').forEach(n => n.style("background-color", PKG_COLOR));
  el.heatmapLegend.classList.toggle("legend-hidden", !state.heatmap);
}

function highlightNode(node) {
  cy.elements().removeClass("selected dimmed highlighted");
  cy.elements(":visible").addClass("dimmed");
  node.closedNeighborhood(":visible").removeClass("dimmed").addClass("highlighted");
  node.addClass("selected");
}

/* ============================================================
   Selection details
   ============================================================ */

function renderSelection(node) {
  const outgoing = node.outgoers("edge:visible").targets().map(t => t.data("label")).slice(0, 6);
  const incoming = node.incomers("edge:visible").sources().map(s => s.data("label")).slice(0, 6);
  const outTotal = node.data("outgoing") ?? 0;
  const inTotal  = node.data("incoming") ?? 0;
  const cImports = node.data("complexityImports") ?? 0;
  const cScore   = Math.round((node.data("complexityScore") ?? 0) * 100);

  const depsHtml = (items, total, arrow) => {
    if (!items.length) return "";
    const more = total - items.length;
    return `<ul class="sel-deps-list">
      ${items.map(s => `<li><span class="arrow">${arrow}</span>${escHtml(s)}</li>`).join("")}
      ${more > 0 ? `<li><span class="arrow">${arrow}</span>+ ${more} more</li>` : ""}
    </ul>`;
  };

  const nodeId = node.id();
  el.selectionInfo.innerHTML = `
    <div class="selection-grid">
      <div class="sel-cell"><div class="lbl">Type</div><div class="val">${escHtml(node.data("type"))}</div></div>
      <div class="sel-cell"><div class="lbl">Language</div><div class="val">${escHtml(node.data("language") ?? "—")}</div></div>
      <div class="sel-cell"><div class="lbl">Inbound</div><div class="val">${inTotal}</div></div>
      <div class="sel-cell"><div class="lbl">Outbound</div><div class="val">${outTotal}</div></div>
    </div>
    <div class="sel-row"><span class="k">Folder</span><span class="v">${escHtml(node.data("folder") ?? "—")}</span></div>
    <div class="sel-row"><span class="k">Complexity</span><span class="v">${cImports} imports · ${cScore}%</span></div>
    <div class="sel-row"><span class="k">In cycle</span><span class="v">${node.data("isCircular") ? "yes" : "no"}</span></div>
    ${outgoing.length ? `<div class="sel-section-title">Depends on (${outTotal})</div>${depsHtml(outgoing, outTotal, "→")}` : ""}
    ${incoming.length ? `<div class="sel-section-title">Used by (${inTotal})</div>${depsHtml(incoming, inTotal, "←")}` : ""}
    <div style="margin-top:10px">
      <button class="trace-from-btn" id="traceFromHereBtn">
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 12h4m0 0V7m0 5v5"/></svg>
        ${escHtml(t("navTrace"))}
      </button>
    </div>
  `;
  document.getElementById("traceFromHereBtn")?.addEventListener("click", () => traceFromNodeId(nodeId));
}

/* ============================================================
   Navigation — left panel views
   ============================================================ */

const LP_NAV = {
  graph:   ["lpGraph",    "navBtnGraph",    "rail-btn-active"],
  insights:["lpInsights", "navBtnInsights", "rail-btn-active"],
  rules:   ["lpRules",    "navBtnRules",    "rail-btn-active"],
  trace:   ["lpTrace",    "navBtnTrace",    "rail-btn-active"],
  advisor: ["lpAdvisor",  "navBtnAdvisor",  "rail-btn-active"],
  config:  ["lpConfig",   "navBtnConfig",   "rail-btn-active"],
};

function switchLeftView(key) {
  for (const [k, [viewId, btnId, activeClass]] of Object.entries(LP_NAV)) {
    document.getElementById(viewId)?.classList.toggle("lp-hidden", k !== key);
    document.getElementById(btnId)?.classList.toggle(activeClass, k === key);
  }
  if (key === "insights" && reportData) renderInsights(reportData);
  if (key === "rules"    && reportData) renderRules(reportData);
  if (key === "advisor"  && reportData) renderAdvisorView(reportData);
}

/* ============================================================
   Navigation — canvas tabs
   ============================================================ */

const CV_TABS = {
  graph:  { btn: "canvasTabGraph",  view: "graph",      title: "Dependency Graph" },
  layers: { btn: "canvasTabLayers", view: "layersView",  title: "Layer Diagram"    },
  matrix: { btn: "canvasTabMatrix", view: "matrixView",  title: "Dependency Matrix"},
};

function switchCanvasTab(key) {
  for (const [k, cfg] of Object.entries(CV_TABS)) {
    document.getElementById(cfg.view)?.classList.toggle("canvas-view-hidden", k !== key);
    document.getElementById(cfg.btn)?.classList.toggle("active", k === key);
  }
  const title = CV_TABS[key]?.title ?? key;
  const breadEl = document.getElementById("breadcrumbView");
  const titleEl = document.getElementById("canvasTitle");
  if (breadEl) breadEl.textContent = title;
  if (titleEl) titleEl.textContent = title;

  if (key === "layers" && reportData) initLayersView(reportData);
  if (key === "matrix" && reportData) renderMatrix(reportData);
}

/* ============================================================
   Layers view
   ============================================================ */

function initLayersView(report) {
  if (cyLayers) { cyLayers.destroy(); cyLayers = null; }
  const container = document.getElementById("layersCy");
  if (!container) return;

  cyLayers = cytoscape({
    container,
    elements: [
      ...report.nodes.map(n => ({ data: { id: n.id, label: n.label, type: n.type, isCircular: Boolean(n.isCircular) } })),
      ...report.edges.map(e => ({ data: { id: e.id, source: e.source, target: e.target, isCircular: Boolean(e.isCircular) } })),
    ],
    wheelSensitivity: 0.2,
    style: buildStylesheet(),
    layout: { name: "breadthfirst", directed: true, animate: true, fit: true, padding: 48, spacingFactor: 1.3, maximal: true },
  });

  const legend = document.getElementById("layersLegend");
  if (legend) {
    legend.innerHTML = `
      <div class="layers-legend-title">Legend</div>
      <div class="layers-legend-row"><span class="swatch" style="background:var(--file-node)"></span>File module</div>
      <div class="layers-legend-row"><span class="swatch" style="background:var(--pkg-node)"></span>Package</div>
      <div class="layers-legend-row"><span class="swatch" style="background:var(--cycle)"></span>In cycle</div>
    `;
  }
}

/* ============================================================
   Matrix view
   ============================================================ */

function renderMatrix(report) {
  const scroll = document.getElementById("matrixScroll");
  if (!scroll) return;

  const fileNodes = report.nodes
    .filter(n => n.type === "file")
    .sort((a, b) => ((b.outgoing ?? 0) + (b.incoming ?? 0)) - ((a.outgoing ?? 0) + (a.incoming ?? 0)))
    .slice(0, 25);

  if (fileNodes.length === 0) {
    scroll.innerHTML = `<p style="color:var(--muted);font-size:12px;padding:12px 0">No file nodes to display.</p>`;
    return;
  }

  const nodeIds = new Set(fileNodes.map(n => n.id));
  const edgeMap = new Map();
  for (const e of report.edges) {
    if (nodeIds.has(e.source) && nodeIds.has(e.target))
      edgeMap.set(`${e.source}\x00${e.target}`, e.isCircular ? "circular" : "dep");
  }

  const short = id => id.replace(/\\/g, "/").split("/").pop() || id;

  const hdr = `<tr><th></th>${fileNodes.map(n => `<th title="${escHtml(n.id)}"><span>${escHtml(short(n.id))}</span></th>`).join("")}</tr>`;
  const body = fileNodes.map(row => {
    const cells = fileNodes.map(col => {
      if (row.id === col.id) return `<td class="mx-cell self-dep" title="self"></td>`;
      const t = edgeMap.get(`${row.id}\x00${col.id}`);
      return t
        ? `<td class="mx-cell ${t}" title="${escHtml(short(row.id))} → ${escHtml(short(col.id))}"></td>`
        : `<td class="mx-cell"></td>`;
    }).join("");
    return `<tr><th title="${escHtml(row.id)}">${escHtml(short(row.id))}</th>${cells}</tr>`;
  }).join("");

  scroll.innerHTML = `<table class="mx-table"><thead>${hdr}</thead><tbody>${body}</tbody></table>`;
}

/* ============================================================
   Insights view
   ============================================================ */

function renderInsights(report) {
  const container = document.getElementById("insightsContent");
  if (!container) return;
  const m = report.metrics ?? {};
  const score = Math.round(m.architectureHealthScore ?? 100);
  const items = [
    { label: t("insHealthScore"),    val: `${score}/100` },
    { label: t("insFilesAnalyzed"),  val: m.filesAnalyzed ?? 0 },
    { label: t("insTotalDeps"),      val: m.totalDependencies ?? 0 },
    { label: t("insCircularDeps"),   val: m.circularDependencyCount ?? 0 },
    { label: t("insExternalPkgs"),   val: m.externalDependencies ?? 0 },
    { label: t("insRuleViols"),      val: m.architectureRuleViolations ?? 0 },
    { label: t("insAvgComplex"),     val: `${((m.complexity?.avgComplexityScore ?? 0) * 100).toFixed(1)}%` },
    { label: t("insCriticalFiles"),  val: (m.criticalFiles ?? []).length },
    { label: t("insResolutionRate"), val: `${Math.round((m.resolutionRate ?? 1) * 100)}%` },
  ];
  container.innerHTML = `<div class="insights-summary">${items.map(i =>
    `<div class="insight-item"><p class="ins-label">${escHtml(i.label)}</p><p class="ins-val">${escHtml(String(i.val))}</p></div>`
  ).join("")}</div>`;
}

/* ============================================================
   Rules view
   ============================================================ */

function renderRules(report) {
  const container = document.getElementById("rulesContent");
  if (!container) return;
  const viols = report.metrics?.architectureRuleViolations ?? 0;
  const layers = report.layers ?? [];

  if (layers.length === 0) {
    container.innerHTML = `
      <div class="rule-card">
        <div class="rule-card-head">
          <svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
          ${escHtml(t("ruleArchLayers"))}
        </div>
        <div class="rule-card-body">${t("ruleNoLayers")}</div>
      </div>
      <div class="rule-card" style="margin-top:0">
        <div class="rule-card-head">
          <svg viewBox="0 0 24 24"><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>
          ${escHtml(t("ruleViolations"))}
        </div>
        <div class="rule-card-body">${viols > 0 ? `${viols} — ${escHtml(t("ruleViolations"))}` : escHtml(t("ruleNoViols"))}</div>
      </div>`;
    return;
  }

  const cards = layers.map(layer =>
    `<div class="rule-card">
      <div class="rule-card-head">
        <svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
        ${escHtml(layer.name ?? "Layer")}
      </div>
      <div class="rule-card-body">${escHtml(layer.description ?? "")}</div>
    </div>`
  ).join("");
  container.innerHTML = cards;
}

/* ============================================================
   Trace view
   ============================================================ */

function traceFromQuery(query) {
  if (!reportData) return;
  const nodes = reportData.nodes ?? [];
  const q = query.replace(/\\/g, "/").toLowerCase();
  const match = nodes.find(n => n.type === "file" && (
    n.id === q ||
    n.id.toLowerCase() === q ||
    n.id.toLowerCase().endsWith("/" + q) ||
    (n.label ?? "").toLowerCase() === q
  ));
  if (!match) {
    const container = document.getElementById("traceContent");
    if (container) container.innerHTML = `<p style="padding:14px 18px;color:var(--danger);font-size:12.5px"><b>${escHtml(query)}</b> — not found</p>`;
    return;
  }
  traceFromNodeId(match.id);
}

function traceFromNodeId(nodeId) {
  if (!reportData) return;

  const edges = reportData.edges ?? [];
  const outgoing = {};
  for (const e of edges) {
    if (!outgoing[e.source]) outgoing[e.source] = [];
    outgoing[e.source].push(e.target);
  }

  const visited = new Map();
  const queue = [[nodeId, 0]];
  while (queue.length) {
    const [current, depth] = queue.shift();
    if (visited.has(current)) continue;
    visited.set(current, depth);
    for (const neighbor of (outgoing[current] ?? [])) {
      if (!visited.has(neighbor)) queue.push([neighbor, depth + 1]);
    }
  }

  const totalFiles = (reportData.nodes ?? []).filter(n => n.type === "file").length;
  const coveragePct = totalFiles > 0 ? Math.round(visited.size / totalFiles * 100) : 0;

  if (cy) {
    cy.elements().removeClass("selected dimmed highlighted");
    cy.elements(":visible").addClass("dimmed");
    cy.nodes('[type="file"]').forEach(n => n.style("background-color", FILE_COLOR));
    for (const [fid, depth] of visited.entries()) {
      const node = cy.getElementById(fid);
      if (node.length) {
        node.removeClass("dimmed").addClass("highlighted");
        node.style("background-color", TRACE_COLORS[Math.min(depth, TRACE_COLORS.length - 1)]);
      }
    }
  }

  const input = document.getElementById("traceInput");
  if (input) input.value = nodeId;

  switchLeftView("trace");
  _renderTracePanel(nodeId, visited, totalFiles, coveragePct);
}

function _renderTracePanel(entryId, visited, totalFiles, coveragePct) {
  const container = document.getElementById("traceContent");
  if (!container) return;

  const short = id => id.replace(/\\/g, "/").split("/").pop() || id;

  const byDepth = new Map();
  for (const [fid, depth] of visited.entries()) {
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth).push(fid);
  }

  const rows = [...byDepth.entries()]
    .sort((a, b) => a[0] - b[0])
    .flatMap(([depth, files]) => {
      const color = TRACE_COLORS[Math.min(depth, TRACE_COLORS.length - 1)];
      return files.sort().map(f => `
        <div class="trace-item">
          <span class="trace-depth" style="background:${color}">d${depth}</span>
          <span class="trace-file" title="${escHtml(f)}">${escHtml(short(f))}</span>
        </div>`);
    }).join("");

  const unreachable = totalFiles - visited.size;

  container.innerHTML = `
    <div class="card">
      <div class="card-body">
        <div class="trace-stats">
          <div class="trace-stat"><b>${visited.size}</b><small>${escHtml(t("traceReachable"))}</small></div>
          <div class="trace-stat"><b>${unreachable}</b><small>${escHtml(t("traceUnreachable"))}</small></div>
          <div class="trace-stat"><b>${coveragePct}%</b><small>${escHtml(t("traceCoverage"))}</small></div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:0">
      <div class="card-head">
        <span class="ico"><svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 12h4m0 0V7m0 5v5"/></svg></span>
        <h2>${escHtml(t("traceFrom"))} ${escHtml(short(entryId))}</h2>
      </div>
      <div class="card-body trace-list">${rows || `<p style="color:var(--muted);font-size:12px">${escHtml(t("traceNoFiles"))}</p>`}</div>
    </div>`;

  const clearBtn = document.getElementById("traceClearBtn");
  if (clearBtn) {
    clearBtn.style.display = "inline-flex";
    clearBtn.onclick = () => {
      if (cy) {
        cy.elements().removeClass("selected dimmed highlighted");
        cy.nodes('[type="file"]').forEach(n => n.style("background-color", state.heatmap ? n.data("heatColor") : FILE_COLOR));
      }
      container.innerHTML = `<p class="selection-muted" style="padding:16px 18px" data-i18n-html="traceHint">${t("traceHint")}</p>`;
      clearBtn.style.display = "none";
      const input = document.getElementById("traceInput");
      if (input) input.value = "";
    };
  }
}

/* ============================================================
   Advisor view
   ============================================================ */

function renderAdvisorView(report) {
  const container = document.getElementById("advisorContent");
  if (!container) return;

  const metrics   = report.metrics    ?? {};
  const risks     = report.risks      ?? {};
  const arch      = report.architecture ?? {};
  const cycles    = report.cycles     ?? [];
  const health    = arch.health       ?? {};

  const score = health.score ?? Math.round(metrics.architectureHealthScore ?? 100);
  const grade = health.grade ?? "?";

  const issues = [];

  if (cycles.length > 0) {
    issues.push({ level: "high", title: `${cycles.length} circular dependenc${cycles.length !== 1 ? "ies" : "y"}`,
      detail: t("advCyclesDetail") });
  }
  const godMods = risks.god_modules ?? [];
  if (godMods.length > 0) {
    const names = godMods.slice(0, 3).map(g => (g.file ?? "").split("/").pop()).join(", ");
    issues.push({ level: "medium", title: `${godMods.length} god module${godMods.length !== 1 ? "s" : ""}`,
      detail: t("advGodModsDetail").replace("{names}", names) });
  }
  const layerViols = risks.layer_violations ?? [];
  if (layerViols.length > 0) {
    issues.push({ level: "medium", title: `${layerViols.length} layer violation${layerViols.length !== 1 ? "s" : ""}`,
      detail: t("advLayerViolsDetail") });
  }
  const ruleViols = arch.ruleViolations ?? [];
  if (ruleViols.length > 0) {
    issues.push({ level: "medium", title: `${ruleViols.length} custom rule violation${ruleViols.length !== 1 ? "s" : ""}`,
      detail: t("advRuleViolsDetail") });
  }
  if (issues.length === 0) {
    issues.push({ level: "ok", title: t("advNoIssues"), detail: t("advNoIssuesDetail") });
  }

  const badge = lvl => lvl === "high" ? "!" : lvl === "ok" ? "✓" : "·";
  const issueCards = issues.map(i => `
    <div class="risk-item risk-${i.level}">
      <div class="risk-badge">${badge(i.level)}</div>
      <div class="risk-body">
        <p class="risk-msg">${escHtml(i.title)}</p>
        <p class="risk-tip">${escHtml(i.detail)}</p>
      </div>
    </div>`).join("");

  container.innerHTML = `
    <div class="card">
      <div class="card-head">
        <span class="ico"><svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9-6-18-3 9H2"/></svg></span>
        <h2>${escHtml(t("advHealthTitle"))} ${score}/100 (${escHtml(grade)})</h2>
      </div>
      <div class="card-body--list">${issueCards}</div>
    </div>
    <div class="card" style="margin-top:0">
      <div class="card-head">
        <span class="ico" style="background:var(--accent-soft);color:var(--accent)"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
        <h2>${escHtml(t("navAdvisor"))}</h2>
      </div>
      <div class="card-body">
        <p style="font-size:12px;color:var(--muted);margin-bottom:10px">${escHtml(t("advGetAdviceDesc"))}</p>
        <div class="advisor-form" id="advisorForm">
          <div class="advisor-field">
            <label class="advisor-label">${escHtml(t("advisorProvider"))}</label>
            <select class="advisor-select" id="advisorProvider">
              <option value="ollama" selected>Ollama (local)</option>
              <option value="claude">Claude</option>
              <option value="openai">OpenAI</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div class="advisor-field">
            <label class="advisor-label">${escHtml(t("advisorModel"))}</label>
            <input class="advisor-input" id="advisorModel" type="text" value="llama3" placeholder="e.g. llama3, claude-opus-4-7"/>
          </div>
          <div class="advisor-field" id="advisorBaseUrlRow">
            <label class="advisor-label">${escHtml(t("advisorBaseUrl"))}</label>
            <input class="advisor-input" id="advisorBaseUrl" type="text" value="http://localhost:11434" placeholder="e.g. http://localhost:11434 or .../v1beta/openai"/>
          </div>
          <div class="advisor-field" id="advisorApiKeyRow" style="display:none">
            <label class="advisor-label">${escHtml(t("advisorApiKey"))}</label>
            <input class="advisor-input" id="advisorApiKey" type="password" placeholder="sk-… (optional for custom)"/>
          </div>
          <button class="advisor-btn" id="advisorRunBtn" type="button">${escHtml(t("advisorGetAdvice"))}</button>
        </div>
        <div id="advisorResult" style="margin-top:12px"></div>
        <details style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px">
          <summary style="font-size:11.5px;font-weight:600;color:var(--ink-2);cursor:pointer">${escHtml(t("advisorCli"))}</summary>
          <div class="advisor-cmds" style="margin-top:8px">
            <code class="advisor-cmd">archmap advise .</code>
            <code class="advisor-cmd">archmap advise . --provider ollama</code>
            <code class="advisor-cmd">archmap advise . --provider openai</code>
            <code class="advisor-cmd">archmap advise . --provider custom --base-url http://localhost:1234</code>
          </div>
          <div style="margin-top:8px">
            <p style="font-size:11.5px;font-weight:600;color:var(--ink-2);margin-bottom:4px">Generate blueprint from real graph</p>
            <code class="advisor-cmd">archmap init --from-analysis</code>
          </div>
        </details>
      </div>
    </div>`;

  _initAdvisorForm();
}

/* ============================================================
   Graph export
   ============================================================ */

function exportGraphPng() {
  if (!cy) return;
  const uri = cy.png({ scale: 2, full: true, output: "base64uri" });
  const a = document.createElement("a");
  a.href = uri;
  a.download = "archmap-graph.png";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function exportGraphSvg() {
  if (!cy) return;
  const svgContent = cy.svg({ full: true });
  const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "archmap-graph.svg";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ============================================================
   i18n — translations & engine
   ============================================================ */

const _TRANSLATIONS = {
  en: {
    navGraph:"Graph view",navInsights:"Insights",navRules:"Rules & Layers",navTrace:"Trace reachability",navAdvisor:"AI Advisor",navOpenProject:"Open project",navToggleTheme:"Toggle theme",navSettings:"Settings",
    serviceMap:"Service Map",serviceMapSub:"Dependency topology and architectural risk hotspots.",
    archHealth:"Architecture Health",cycles:"Cycles",layerViol:"Layer viol.",godFiles:"God files",avgComplex:"Avg complex.",
    risksAnomalies:"Risks & Anomalies",graphControls:"Graph Controls",filterByFolder:"Filter by folder",onlyCircular:"Only circular dependencies",heatmapMode:"Heatmap (complexity)",
    zoomIn:"Zoom +",zoomOut:"Zoom −",fit:"Fit",relayout:"Relayout",clearHighlight:"Clear highlight",criticalFiles:"Critical files",
    insightsTitle:"Architecture Report",insightsSub:"AI-generated analysis of your codebase structure.",
    insHealthScore:"Health score",insFilesAnalyzed:"Files analysed",insTotalDeps:"Total dependencies",insCircularDeps:"Circular dependencies",insExternalPkgs:"External packages",insRuleViols:"Rule violations",insAvgComplex:"Avg complexity",insCriticalFiles:"Critical files",
    rulesTitle:"Architecture Rules",rulesSub:"Layer hierarchy, violations, and structural constraints.",
    ruleArchLayers:"Architecture layers",ruleNoLayers:"No layer rules configured. Add an <code>.archmap.toml</code> file to define your architecture layers and dependency rules.",ruleViolations:"Violations",ruleNoViols:"No violations detected.",
    traceTitle:"Reachability",traceSub:"BFS from an entrypoint through all dependency edges.",tracePlaceholder:"File path or name…",traceBtn:"Trace",traceClear:"Clear highlight",
    traceHint:"Select a node on the graph and click <b>Trace from here</b>, or type a file name above.",
    traceReachable:"reachable",traceUnreachable:"unreachable",traceCoverage:"coverage",traceNoFiles:"No files reachable.",traceFrom:"From:",
    advisorTitle:"Advice",advisorSub:"Top issues and commands for LLM-powered architectural advice.",
    advisorProvider:"Provider",advisorModel:"Model",advisorBaseUrl:"Base URL",advisorApiKey:"API Key",advisorGetAdvice:"Get Advice",advisorRequesting:"Requesting…",advisorWaiting:"⏳ Waiting for LLM response…",advisorCli:"CLI commands",
    advHealthTitle:"Health",advGetAdviceDesc:"Get concrete refactoring advice from your LLM of choice — runs directly from the browser.",
    advNoIssues:"No architectural issues detected",advNoIssuesDetail:"Architecture looks clean. Keep monitoring as the project grows.",
    advCyclesDetail:"Cycles prevent modular refactoring and increase coupling. Break them via interface extraction or dependency inversion.",
    advGodModsDetail:"Files with excessive dependents: {names}. Consider splitting into smaller focused modules.",
    advLayerViolsDetail:"Dependencies cross layer boundaries in forbidden directions. Check your .archmap.toml.",
    advRuleViolsDetail:"One or more architecture rules defined in .archmap.toml are being violated.",
    cfgTitle:"Configuration",cfgSub:"LLM provider, languages, and preferences.",cfgInterface:"Interface",cfgLangLabel:"Language",
    cfgGeneral:"General",cfgAutoSaveLabel:"Auto-save config",cfgAutoSaveDesc:"Save LLM settings automatically as you type.",cfgAnimations:"Enable animations",
    cfgGraph:"Graph",cfgDefaultLayout:"Default layout",cfgLlmAdvisor:"LLM Advisor",cfgScanLangs:"Scan Languages",cfgScanLangsDesc:"Languages included in the architectural analysis.",cfgSave:"Save",cfgSaved:"Saved ✓",
    canvasGraph:"Graph",canvasLayers:"Layers",canvasMatrix:"Matrix",dependencyGraph:"Dependency Graph",layerDiagram:"Layer Diagram",dependencyMatrix:"Dependency Matrix",
    searchPlaceholder:"Search files or packages",refresh:"Refresh",miniMap:"Mini map",
    matrixTitle:"Dependency Matrix",matrixSub:"Top files by connectivity · rows = source · columns = target",matrixDep:"Dependency",matrixCircular:"Circular",matrixSelf:"Self",
    summary:"Summary",selection:"Selection",selectionHint:"Click a node to inspect dependencies.",circularDeps:"Circular deps",
    heatmapLegend:"Heatmap legend",heatmapDesc:'Toggle "Heatmap mode" to color nodes by import complexity.',heatLow:"Low",heatMid:"Medium",heatHigh:"High",
    statusFile:"File",statusPkg:"Package",statusCycle:"Cycle",loading:"Loading…",
    insResolutionRate:"Resolution rate",exportPng:"PNG",exportSvg:"SVG",
  },
  pt: {
    navGraph:"Grafo",navInsights:"Insights",navRules:"Regras & Camadas",navTrace:"Rastrear dependências",navAdvisor:"Consultor IA",navOpenProject:"Abrir projeto",navToggleTheme:"Alternar tema",navSettings:"Configurações",
    serviceMap:"Mapa de Serviços",serviceMapSub:"Topologia de dependências e hotspots de risco arquitetural.",
    archHealth:"Saúde da Arquitetura",cycles:"Ciclos",layerViol:"Viol. de camada",godFiles:"Arquivos deus",avgComplex:"Complex. média",
    risksAnomalies:"Riscos & Anomalias",graphControls:"Controles do Grafo",filterByFolder:"Filtrar por pasta",onlyCircular:"Apenas dependências circulares",heatmapMode:"Mapa de calor (complexidade)",
    zoomIn:"Zoom +",zoomOut:"Zoom −",fit:"Ajustar",relayout:"Reorganizar",clearHighlight:"Limpar destaque",criticalFiles:"Arquivos críticos",
    insightsTitle:"Relatório de Arquitetura",insightsSub:"Análise gerada por IA da estrutura do código.",
    insHealthScore:"Pontuação de saúde",insFilesAnalyzed:"Arquivos analisados",insTotalDeps:"Total de dependências",insCircularDeps:"Dependências circulares",insExternalPkgs:"Pacotes externos",insRuleViols:"Violações de regra",insAvgComplex:"Complexidade média",insCriticalFiles:"Arquivos críticos",
    rulesTitle:"Regras de Arquitetura",rulesSub:"Hierarquia de camadas, violações e restrições estruturais.",
    ruleArchLayers:"Camadas de arquitetura",ruleNoLayers:"Nenhuma regra de camada configurada. Adicione um arquivo <code>.archmap.toml</code> para definir suas camadas e regras de dependência.",ruleViolations:"Violações",ruleNoViols:"Nenhuma violação detectada.",
    traceTitle:"Alcançabilidade",traceSub:"BFS a partir de um ponto de entrada por todas as arestas de dependência.",tracePlaceholder:"Caminho ou nome do arquivo…",traceBtn:"Rastrear",traceClear:"Limpar destaque",
    traceHint:"Selecione um nó no grafo e clique em <b>Rastrear a partir daqui</b>, ou digite um nome de arquivo acima.",
    traceReachable:"alcançável",traceUnreachable:"inacessível",traceCoverage:"cobertura",traceNoFiles:"Nenhum arquivo alcançável.",traceFrom:"De:",
    advisorTitle:"Conselho",advisorSub:"Principais problemas e comandos para conselho arquitetural com LLM.",
    advisorProvider:"Provedor",advisorModel:"Modelo",advisorBaseUrl:"URL Base",advisorApiKey:"Chave de API",advisorGetAdvice:"Obter Conselho",advisorRequesting:"Solicitando…",advisorWaiting:"⏳ Aguardando resposta do LLM…",advisorCli:"Comandos CLI",
    advHealthTitle:"Saúde",advGetAdviceDesc:"Obtenha conselhos concretos de refatoração do seu LLM — direto do navegador.",
    advNoIssues:"Nenhum problema arquitetural detectado",advNoIssuesDetail:"A arquitetura parece limpa. Continue monitorando conforme o projeto cresce.",
    advCyclesDetail:"Ciclos impedem refatoração modular e aumentam o acoplamento. Quebre-os via extração de interface ou inversão de dependência.",
    advGodModsDetail:"Arquivos com dependentes excessivos: {names}. Considere dividir em módulos menores.",
    advLayerViolsDetail:"Dependências cruzam limites de camadas em direções proibidas. Verifique seu .archmap.toml.",
    advRuleViolsDetail:"Uma ou mais regras de arquitetura definidas no .archmap.toml estão sendo violadas.",
    cfgTitle:"Configuração",cfgSub:"Provedor LLM, linguagens e preferências.",cfgInterface:"Interface",cfgLangLabel:"Idioma",
    cfgGeneral:"Geral",cfgAutoSaveLabel:"Salvar automaticamente",cfgAutoSaveDesc:"Salva as configurações do LLM automaticamente ao digitar.",cfgAnimations:"Ativar animações",
    cfgGraph:"Grafo",cfgDefaultLayout:"Layout padrão",cfgLlmAdvisor:"Consultor LLM",cfgScanLangs:"Linguagens para Análise",cfgScanLangsDesc:"Linguagens incluídas na análise arquitetural.",cfgSave:"Salvar",cfgSaved:"Salvo ✓",
    canvasGraph:"Grafo",canvasLayers:"Camadas",canvasMatrix:"Matriz",dependencyGraph:"Grafo de Dependências",layerDiagram:"Diagrama de Camadas",dependencyMatrix:"Matriz de Dependências",
    searchPlaceholder:"Buscar arquivos ou pacotes",refresh:"Atualizar",miniMap:"Minimapa",
    matrixTitle:"Matriz de Dependências",matrixSub:"Top arquivos por conectividade · linhas = origem · colunas = destino",matrixDep:"Dependência",matrixCircular:"Circular",matrixSelf:"Auto",
    summary:"Resumo",selection:"Seleção",selectionHint:"Clique em um nó para inspecionar dependências.",circularDeps:"Deps. circulares",
    heatmapLegend:"Legenda do mapa de calor",heatmapDesc:'Ative o "Modo mapa de calor" para colorir nós por complexidade.',heatLow:"Baixo",heatMid:"Médio",heatHigh:"Alto",
    statusFile:"Arquivo",statusPkg:"Pacote",statusCycle:"Ciclo",loading:"Carregando…",
    insResolutionRate:"Taxa de resolução",exportPng:"PNG",exportSvg:"SVG",
  },
  es: {
    navGraph:"Vista de grafo",navInsights:"Perspectivas",navRules:"Reglas y Capas",navTrace:"Rastrear dependencias",navAdvisor:"Asesor IA",navOpenProject:"Abrir proyecto",navToggleTheme:"Cambiar tema",navSettings:"Configuración",
    serviceMap:"Mapa de Servicios",serviceMapSub:"Topología de dependencias y puntos críticos de riesgo arquitectónico.",
    archHealth:"Salud de la Arquitectura",cycles:"Ciclos",layerViol:"Viol. de capa",godFiles:"Archivos dios",avgComplex:"Compl. promedio",
    risksAnomalies:"Riesgos y Anomalías",graphControls:"Controles del Grafo",filterByFolder:"Filtrar por carpeta",onlyCircular:"Solo dependencias circulares",heatmapMode:"Mapa de calor (complejidad)",
    zoomIn:"Zoom +",zoomOut:"Zoom −",fit:"Ajustar",relayout:"Reorganizar",clearHighlight:"Limpiar resaltado",criticalFiles:"Archivos críticos",
    insightsTitle:"Informe de Arquitectura",insightsSub:"Análisis generado por IA de la estructura del código.",
    insHealthScore:"Puntuación de salud",insFilesAnalyzed:"Archivos analizados",insTotalDeps:"Total de dependencias",insCircularDeps:"Dependencias circulares",insExternalPkgs:"Paquetes externos",insRuleViols:"Violaciones de regla",insAvgComplex:"Complejidad media",insCriticalFiles:"Archivos críticos",
    rulesTitle:"Reglas de Arquitectura",rulesSub:"Jerarquía de capas, violaciones y restricciones estructurales.",
    ruleArchLayers:"Capas de arquitectura",ruleNoLayers:"No hay reglas de capa configuradas. Agregue un archivo <code>.archmap.toml</code> para definir sus capas y reglas de dependencia.",ruleViolations:"Violaciones",ruleNoViols:"No se detectaron violaciones.",
    traceTitle:"Alcanzabilidad",traceSub:"BFS desde un punto de entrada a través de todas las aristas de dependencia.",tracePlaceholder:"Ruta o nombre del archivo…",traceBtn:"Rastrear",traceClear:"Limpiar resaltado",
    traceHint:"Selecciona un nodo en el grafo y haz clic en <b>Rastrear desde aquí</b>, o escribe un nombre de archivo arriba.",
    traceReachable:"alcanzable",traceUnreachable:"inalcanzable",traceCoverage:"cobertura",traceNoFiles:"No hay archivos alcanzables.",traceFrom:"Desde:",
    advisorTitle:"Consejo",advisorSub:"Problemas principales y comandos para consejos arquitectónicos con LLM.",
    advisorProvider:"Proveedor",advisorModel:"Modelo",advisorBaseUrl:"URL Base",advisorApiKey:"Clave de API",advisorGetAdvice:"Obtener Consejo",advisorRequesting:"Solicitando…",advisorWaiting:"⏳ Esperando respuesta del LLM…",advisorCli:"Comandos CLI",
    advHealthTitle:"Salud",advGetAdviceDesc:"Obtén consejos concretos de refactorización de tu LLM — directamente desde el navegador.",
    advNoIssues:"No se detectaron problemas arquitectónicos",advNoIssuesDetail:"La arquitectura parece limpia. Sigue monitoreando conforme crece el proyecto.",
    advCyclesDetail:"Los ciclos impiden la refactorización modular y aumentan el acoplamiento. Rómpelos mediante extracción de interfaces o inversión de dependencias.",
    advGodModsDetail:"Archivos con dependientes excesivos: {names}. Considera dividirlos en módulos más pequeños.",
    advLayerViolsDetail:"Las dependencias cruzan límites de capas en direcciones prohibidas. Revisa tu .archmap.toml.",
    advRuleViolsDetail:"Una o más reglas de arquitectura definidas en .archmap.toml están siendo violadas.",
    cfgTitle:"Configuración",cfgSub:"Proveedor LLM, idiomas y preferencias.",cfgInterface:"Interfaz",cfgLangLabel:"Idioma",
    cfgGeneral:"General",cfgAutoSaveLabel:"Guardado automático",cfgAutoSaveDesc:"Guarda la configuración del LLM automáticamente al escribir.",cfgAnimations:"Activar animaciones",
    cfgGraph:"Grafo",cfgDefaultLayout:"Diseño predeterminado",cfgLlmAdvisor:"Asesor LLM",cfgScanLangs:"Lenguajes de Análisis",cfgScanLangsDesc:"Lenguajes incluidos en el análisis arquitectónico.",cfgSave:"Guardar",cfgSaved:"Guardado ✓",
    canvasGraph:"Grafo",canvasLayers:"Capas",canvasMatrix:"Matriz",dependencyGraph:"Grafo de Dependencias",layerDiagram:"Diagrama de Capas",dependencyMatrix:"Matriz de Dependencias",
    searchPlaceholder:"Buscar archivos o paquetes",refresh:"Actualizar",miniMap:"Minimapa",
    matrixTitle:"Matriz de Dependencias",matrixSub:"Top archivos por conectividad · filas = origen · columnas = destino",matrixDep:"Dependencia",matrixCircular:"Circular",matrixSelf:"Auto",
    summary:"Resumen",selection:"Selección",selectionHint:"Haz clic en un nodo para inspeccionar dependencias.",circularDeps:"Deps. circulares",
    heatmapLegend:"Leyenda del mapa de calor",heatmapDesc:'Activa el "Modo mapa de calor" para colorear nodos por complejidad.',heatLow:"Bajo",heatMid:"Medio",heatHigh:"Alto",
    statusFile:"Archivo",statusPkg:"Paquete",statusCycle:"Ciclo",loading:"Cargando…",
    insResolutionRate:"Tasa de resolución",exportPng:"PNG",exportSvg:"SVG",
  },
  fr: {
    navGraph:"Vue graphe",navInsights:"Insights",navRules:"Règles & Couches",navTrace:"Tracer les dépendances",navAdvisor:"Conseiller IA",navOpenProject:"Ouvrir le projet",navToggleTheme:"Changer le thème",navSettings:"Paramètres",
    serviceMap:"Carte des Services",serviceMapSub:"Topologie des dépendances et points chauds de risque architectural.",
    archHealth:"Santé de l'Architecture",cycles:"Cycles",layerViol:"Viol. de couche",godFiles:"Fichiers dieu",avgComplex:"Complex. moy.",
    risksAnomalies:"Risques & Anomalies",graphControls:"Contrôles du Graphe",filterByFolder:"Filtrer par dossier",onlyCircular:"Uniquement dépendances circulaires",heatmapMode:"Carte de chaleur (complexité)",
    zoomIn:"Zoom +",zoomOut:"Zoom −",fit:"Ajuster",relayout:"Réorganiser",clearHighlight:"Effacer le surlignage",criticalFiles:"Fichiers critiques",
    insightsTitle:"Rapport d'Architecture",insightsSub:"Analyse générée par IA de la structure du code.",
    insHealthScore:"Score de santé",insFilesAnalyzed:"Fichiers analysés",insTotalDeps:"Total des dépendances",insCircularDeps:"Dépendances circulaires",insExternalPkgs:"Paquets externes",insRuleViols:"Violations de règle",insAvgComplex:"Complexité moyenne",insCriticalFiles:"Fichiers critiques",
    rulesTitle:"Règles d'Architecture",rulesSub:"Hiérarchie des couches, violations et contraintes structurelles.",
    ruleArchLayers:"Couches d'architecture",ruleNoLayers:"Aucune règle de couche configurée. Ajoutez un fichier <code>.archmap.toml</code> pour définir vos couches et règles de dépendance.",ruleViolations:"Violations",ruleNoViols:"Aucune violation détectée.",
    traceTitle:"Atteignabilité",traceSub:"BFS depuis un point d'entrée à travers toutes les arêtes de dépendance.",tracePlaceholder:"Chemin ou nom du fichier…",traceBtn:"Tracer",traceClear:"Effacer le surlignage",
    traceHint:"Sélectionnez un nœud sur le graphe et cliquez sur <b>Tracer depuis ici</b>, ou tapez un nom de fichier ci-dessus.",
    traceReachable:"atteignable",traceUnreachable:"inaccessible",traceCoverage:"couverture",traceNoFiles:"Aucun fichier atteignable.",traceFrom:"De :",
    advisorTitle:"Conseils",advisorSub:"Principaux problèmes et commandes pour des conseils architecturaux avec LLM.",
    advisorProvider:"Fournisseur",advisorModel:"Modèle",advisorBaseUrl:"URL de base",advisorApiKey:"Clé API",advisorGetAdvice:"Obtenir des Conseils",advisorRequesting:"Requête en cours…",advisorWaiting:"⏳ En attente de la réponse du LLM…",advisorCli:"Commandes CLI",
    advHealthTitle:"Santé",advGetAdviceDesc:"Obtenez des conseils de refactorisation concrets de votre LLM — directement depuis le navigateur.",
    advNoIssues:"Aucun problème architectural détecté",advNoIssuesDetail:"L'architecture semble propre. Continuez à surveiller la croissance du projet.",
    advCyclesDetail:"Les cycles empêchent la refactorisation modulaire et augmentent le couplage. Brisez-les via l'extraction d'interface ou l'inversion de dépendance.",
    advGodModsDetail:"Fichiers avec des dépendants excessifs : {names}. Envisagez de les diviser en modules plus petits.",
    advLayerViolsDetail:"Les dépendances traversent les limites de couches dans des directions interdites. Vérifiez votre .archmap.toml.",
    advRuleViolsDetail:"Une ou plusieurs règles d'architecture définies dans .archmap.toml sont violées.",
    cfgTitle:"Configuration",cfgSub:"Fournisseur LLM, langages et préférences.",cfgInterface:"Interface",cfgLangLabel:"Langue",
    cfgGeneral:"Général",cfgAutoSaveLabel:"Sauvegarde automatique",cfgAutoSaveDesc:"Sauvegarde les paramètres LLM automatiquement lors de la saisie.",cfgAnimations:"Activer les animations",
    cfgGraph:"Graphe",cfgDefaultLayout:"Disposition par défaut",cfgLlmAdvisor:"Conseiller LLM",cfgScanLangs:"Langages d'Analyse",cfgScanLangsDesc:"Langages inclus dans l'analyse architecturale.",cfgSave:"Enregistrer",cfgSaved:"Enregistré ✓",
    canvasGraph:"Graphe",canvasLayers:"Couches",canvasMatrix:"Matrice",dependencyGraph:"Graphe de Dépendances",layerDiagram:"Diagramme de Couches",dependencyMatrix:"Matrice de Dépendances",
    searchPlaceholder:"Rechercher des fichiers ou paquets",refresh:"Actualiser",miniMap:"Mini carte",
    matrixTitle:"Matrice de Dépendances",matrixSub:"Top fichiers par connectivité · lignes = source · colonnes = cible",matrixDep:"Dépendance",matrixCircular:"Circulaire",matrixSelf:"Auto",
    summary:"Résumé",selection:"Sélection",selectionHint:"Cliquez sur un nœud pour inspecter les dépendances.",circularDeps:"Dép. circulaires",
    heatmapLegend:"Légende de la carte de chaleur",heatmapDesc:"Activez le mode carte de chaleur pour colorier les nœuds par complexité.",heatLow:"Bas",heatMid:"Moyen",heatHigh:"Élevé",
    statusFile:"Fichier",statusPkg:"Paquet",statusCycle:"Cycle",loading:"Chargement…",
    insResolutionRate:"Taux de résolution",exportPng:"PNG",exportSvg:"SVG",
  },
  de: {
    navGraph:"Graphansicht",navInsights:"Einblicke",navRules:"Regeln & Schichten",navTrace:"Abhängigkeiten verfolgen",navAdvisor:"KI-Berater",navOpenProject:"Projekt öffnen",navToggleTheme:"Design wechseln",navSettings:"Einstellungen",
    serviceMap:"Service-Karte",serviceMapSub:"Abhängigkeitstopologie und architektonische Risikohotspots.",
    archHealth:"Architektur-Gesundheit",cycles:"Zyklen",layerViol:"Schichtverstöße",godFiles:"Gotdateien",avgComplex:"Ø Komplexität",
    risksAnomalies:"Risiken & Anomalien",graphControls:"Graphsteuerung",filterByFolder:"Nach Ordner filtern",onlyCircular:"Nur zirkuläre Abhängigkeiten",heatmapMode:"Heatmap (Komplexität)",
    zoomIn:"Zoom +",zoomOut:"Zoom −",fit:"Anpassen",relayout:"Neu anordnen",clearHighlight:"Hervorhebung löschen",criticalFiles:"Kritische Dateien",
    insightsTitle:"Architekturbericht",insightsSub:"KI-generierte Analyse der Codebase-Struktur.",
    insHealthScore:"Gesundheitspunktzahl",insFilesAnalyzed:"Analysierte Dateien",insTotalDeps:"Gesamtabhängigkeiten",insCircularDeps:"Zirkuläre Abhängigkeiten",insExternalPkgs:"Externe Pakete",insRuleViols:"Regelverstöße",insAvgComplex:"Ø Komplexität",insCriticalFiles:"Kritische Dateien",
    rulesTitle:"Architekturregeln",rulesSub:"Schichthierarchie, Verstöße und strukturelle Einschränkungen.",
    ruleArchLayers:"Architekturschichten",ruleNoLayers:"Keine Schichtregeln konfiguriert. Fügen Sie eine <code>.archmap.toml</code>-Datei hinzu, um Ihre Schichten und Abhängigkeitsregeln zu definieren.",ruleViolations:"Verstöße",ruleNoViols:"Keine Verstöße erkannt.",
    traceTitle:"Erreichbarkeit",traceSub:"BFS von einem Einstiegspunkt durch alle Abhängigkeitskanten.",tracePlaceholder:"Dateipfad oder Name…",traceBtn:"Verfolgen",traceClear:"Hervorhebung löschen",
    traceHint:"Wählen Sie einen Knoten im Graphen und klicken Sie auf <b>Von hier verfolgen</b>, oder geben Sie oben einen Dateinamen ein.",
    traceReachable:"erreichbar",traceUnreachable:"nicht erreichbar",traceCoverage:"Abdeckung",traceNoFiles:"Keine Dateien erreichbar.",traceFrom:"Von:",
    advisorTitle:"Beratung",advisorSub:"Hauptprobleme und Befehle für LLM-gestützte Architekturberatung.",
    advisorProvider:"Anbieter",advisorModel:"Modell",advisorBaseUrl:"Basis-URL",advisorApiKey:"API-Schlüssel",advisorGetAdvice:"Beratung abrufen",advisorRequesting:"Wird angefordert…",advisorWaiting:"⏳ Warte auf LLM-Antwort…",advisorCli:"CLI-Befehle",
    advHealthTitle:"Gesundheit",advGetAdviceDesc:"Holen Sie sich konkrete Refactoring-Ratschläge von Ihrem LLM — direkt im Browser.",
    advNoIssues:"Keine Architekturprobleme erkannt",advNoIssuesDetail:"Die Architektur sieht sauber aus. Überwachen Sie weiterhin das Projektwachstum.",
    advCyclesDetail:"Zyklen verhindern modulares Refactoring und erhöhen die Kopplung. Brechen Sie sie durch Interface-Extraktion oder Dependency Inversion.",
    advGodModsDetail:"Dateien mit übermäßigen Abhängigen: {names}. Erwägen Sie, sie in kleinere Module aufzuteilen.",
    advLayerViolsDetail:"Abhängigkeiten überschreiten Schichtgrenzen in verbotenen Richtungen. Prüfen Sie Ihre .archmap.toml.",
    advRuleViolsDetail:"Eine oder mehrere Architekturregeln in .archmap.toml werden verletzt.",
    cfgTitle:"Konfiguration",cfgSub:"LLM-Anbieter, Sprachen und Einstellungen.",cfgInterface:"Oberfläche",cfgLangLabel:"Sprache",
    cfgGeneral:"Allgemein",cfgAutoSaveLabel:"Automatisch speichern",cfgAutoSaveDesc:"LLM-Einstellungen beim Tippen automatisch speichern.",cfgAnimations:"Animationen aktivieren",
    cfgGraph:"Graph",cfgDefaultLayout:"Standardlayout",cfgLlmAdvisor:"LLM-Berater",cfgScanLangs:"Analysesprachen",cfgScanLangsDesc:"Sprachen, die in der Architekturanalyse enthalten sind.",cfgSave:"Speichern",cfgSaved:"Gespeichert ✓",
    canvasGraph:"Graph",canvasLayers:"Schichten",canvasMatrix:"Matrix",dependencyGraph:"Abhängigkeitsgraph",layerDiagram:"Schichtdiagramm",dependencyMatrix:"Abhängigkeitsmatrix",
    searchPlaceholder:"Dateien oder Pakete suchen",refresh:"Aktualisieren",miniMap:"Minikarte",
    matrixTitle:"Abhängigkeitsmatrix",matrixSub:"Top-Dateien nach Konnektivität · Zeilen = Quelle · Spalten = Ziel",matrixDep:"Abhängigkeit",matrixCircular:"Zirkulär",matrixSelf:"Selbst",
    summary:"Zusammenfassung",selection:"Auswahl",selectionHint:"Klicken Sie auf einen Knoten, um Abhängigkeiten zu prüfen.",circularDeps:"Zirk. Abhängigkeiten",
    heatmapLegend:"Heatmap-Legende",heatmapDesc:'Aktivieren Sie den "Heatmap-Modus" um Knoten nach Importkomplexität zu färben.',heatLow:"Niedrig",heatMid:"Mittel",heatHigh:"Hoch",
    statusFile:"Datei",statusPkg:"Paket",statusCycle:"Zyklus",loading:"Wird geladen…",
    insResolutionRate:"Auflösungsrate",exportPng:"PNG",exportSvg:"SVG",
  },
  zh: {
    navGraph:"依赖图",navInsights:"洞察",navRules:"规则与层",navTrace:"追踪依赖",navAdvisor:"AI 顾问",navOpenProject:"打开项目",navToggleTheme:"切换主题",navSettings:"设置",
    serviceMap:"服务地图",serviceMapSub:"依赖拓扑和架构风险热点。",
    archHealth:"架构健康度",cycles:"循环",layerViol:"层级违规",godFiles:"上帝文件",avgComplex:"平均复杂度",
    risksAnomalies:"风险与异常",graphControls:"图形控制",filterByFolder:"按文件夹过滤",onlyCircular:"仅循环依赖",heatmapMode:"热力图（复杂度）",
    zoomIn:"放大",zoomOut:"缩小",fit:"适应",relayout:"重新布局",clearHighlight:"清除高亮",criticalFiles:"关键文件",
    insightsTitle:"架构报告",insightsSub:"AI 生成的代码库结构分析。",
    insHealthScore:"健康分数",insFilesAnalyzed:"已分析文件",insTotalDeps:"总依赖数",insCircularDeps:"循环依赖",insExternalPkgs:"外部包",insRuleViols:"规则违规",insAvgComplex:"平均复杂度",insCriticalFiles:"关键文件",
    rulesTitle:"架构规则",rulesSub:"层级结构、违规和结构约束。",
    ruleArchLayers:"架构层",ruleNoLayers:"未配置层规则。添加 <code>.archmap.toml</code> 文件以定义您的架构层和依赖规则。",ruleViolations:"违规",ruleNoViols:"未检测到违规。",
    traceTitle:"可达性",traceSub:"从入口点通过所有依赖边进行广度优先搜索。",tracePlaceholder:"文件路径或名称…",traceBtn:"追踪",traceClear:"清除高亮",
    traceHint:"在图中选择一个节点并点击<b>从这里追踪</b>，或在上方输入文件名。",
    traceReachable:"可达",traceUnreachable:"不可达",traceCoverage:"覆盖率",traceNoFiles:"没有可达的文件。",traceFrom:"从：",
    advisorTitle:"建议",advisorSub:"基于 LLM 的架构建议的主要问题和命令。",
    advisorProvider:"提供商",advisorModel:"模型",advisorBaseUrl:"基础 URL",advisorApiKey:"API 密钥",advisorGetAdvice:"获取建议",advisorRequesting:"请求中…",advisorWaiting:"⏳ 等待 LLM 响应…",advisorCli:"CLI 命令",
    advHealthTitle:"健康度",advGetAdviceDesc:"从您选择的 LLM 获取具体的重构建议——直接在浏览器中运行。",
    advNoIssues:"未检测到架构问题",advNoIssuesDetail:"架构看起来很干净。随着项目增长继续监控。",
    advCyclesDetail:"循环阻止模块化重构并增加耦合。通过接口提取或依赖反转来打破它们。",
    advGodModsDetail:"具有过多依赖者的文件：{names}。考虑将其拆分为更小的模块。",
    advLayerViolsDetail:"依赖在禁止方向上跨越层边界。检查您的 .archmap.toml。",
    advRuleViolsDetail:".archmap.toml 中定义的一个或多个架构规则正在被违反。",
    cfgTitle:"配置",cfgSub:"LLM 提供商、语言和偏好设置。",cfgInterface:"界面",cfgLangLabel:"语言",
    cfgGeneral:"常规",cfgAutoSaveLabel:"自动保存",cfgAutoSaveDesc:"输入时自动保存 LLM 设置。",cfgAnimations:"启用动画",
    cfgGraph:"图形",cfgDefaultLayout:"默认布局",cfgLlmAdvisor:"LLM 顾问",cfgScanLangs:"扫描语言",cfgScanLangsDesc:"包含在架构分析中的语言。",cfgSave:"保存",cfgSaved:"已保存 ✓",
    canvasGraph:"图",canvasLayers:"层",canvasMatrix:"矩阵",dependencyGraph:"依赖图",layerDiagram:"层级图",dependencyMatrix:"依赖矩阵",
    searchPlaceholder:"搜索文件或包",refresh:"刷新",miniMap:"小地图",
    matrixTitle:"依赖矩阵",matrixSub:"按连接度排名的文件 · 行 = 源 · 列 = 目标",matrixDep:"依赖",matrixCircular:"循环",matrixSelf:"自身",
    summary:"摘要",selection:"选择",selectionHint:"点击节点以检查依赖关系。",circularDeps:"循环依赖",
    heatmapLegend:"热力图图例",heatmapDesc:"切换热力图模式以按导入复杂度为节点着色。",heatLow:"低",heatMid:"中",heatHigh:"高",
    statusFile:"文件",statusPkg:"包",statusCycle:"循环",loading:"加载中…",
    insResolutionRate:"解析率",exportPng:"PNG",exportSvg:"SVG",
  },
};

let _currentLang = "en";

function t(key) {
  return _TRANSLATIONS[_currentLang]?.[key] ?? _TRANSLATIONS.en[key] ?? key;
}

function applyI18n() {
  const langMap = { en:"en", pt:"pt-BR", es:"es", fr:"fr", de:"de", zh:"zh-CN" };
  document.getElementById("htmlRoot")?.setAttribute("lang", langMap[_currentLang] ?? "en");

  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const v = t(el.dataset.i18nTitle);
    el.title = v;
    if (el.hasAttribute("aria-label")) el.setAttribute("aria-label", v);
  });

  CV_TABS.graph.title  = t("dependencyGraph");
  CV_TABS.layers.title = t("layerDiagram");
  CV_TABS.matrix.title = t("dependencyMatrix");

  const breadcrumb = document.getElementById("breadcrumbView");
  const canvasTitle = document.getElementById("canvasTitle");
  const activeTab = Object.values(CV_TABS).find(c => document.getElementById(c.btn)?.classList.contains("active"));
  if (activeTab && breadcrumb) breadcrumb.textContent = activeTab.title;
  if (activeTab && canvasTitle) canvasTitle.textContent = activeTab.title;

  if (reportData) {
    const active = Object.entries(LP_NAV).find(([, [vid]]) => !document.getElementById(vid)?.classList.contains("lp-hidden"))?.[0];
    if (active === "insights") renderInsights(reportData);
    if (active === "rules")    renderRules(reportData);
    if (active === "advisor")  renderAdvisorView(reportData);
  }
}

const _ADVISOR_DEFAULTS = {
  ollama:  { model: "llama3",          baseUrl: "http://localhost:11434", showKey: false, showUrl: true  },
  claude:  { model: "claude-opus-4-7", baseUrl: "",                       showKey: true,  showUrl: false },
  openai:  { model: "gpt-4o",          baseUrl: "",                       showKey: true,  showUrl: false },
  custom:  { model: "gemini-1.5-flash", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", showKey: true, showUrl: true },
};

function _initAdvisorForm() {
  const providerEl  = document.getElementById("advisorProvider");
  const modelEl     = document.getElementById("advisorModel");
  const baseUrlEl   = document.getElementById("advisorBaseUrl");
  const apiKeyEl    = document.getElementById("advisorApiKey");
  const baseUrlRow  = document.getElementById("advisorBaseUrlRow");
  const apiKeyRow   = document.getElementById("advisorApiKeyRow");
  const runBtn      = document.getElementById("advisorRunBtn");
  const resultEl    = document.getElementById("advisorResult");
  if (!providerEl || !runBtn) return;

  const _STORAGE_KEY = "archmap.advisor.config";

  function _saveConfig() {
    try {
      localStorage.setItem(_STORAGE_KEY, JSON.stringify({
        provider: providerEl.value,
        model:    modelEl.value.trim(),
        baseUrl:  baseUrlEl.value.trim(),
        apiKey:   apiKeyEl.value.trim(),
      }));
    } catch (_) {}
  }

  function _restoreConfig() {
    try {
      const raw = localStorage.getItem(_STORAGE_KEY);
      if (!raw) return false;
      const cfg = JSON.parse(raw);
      if (cfg.provider && providerEl.querySelector(`option[value="${CSS.escape(cfg.provider)}"]`)) {
        providerEl.value = cfg.provider;
      }
      if (cfg.model)   modelEl.value   = cfg.model;
      if (cfg.baseUrl) baseUrlEl.value = cfg.baseUrl;
      if (cfg.apiKey)  apiKeyEl.value  = cfg.apiKey;
      return true;
    } catch (_) { return false; }
  }

  function applyProviderDefaults(p) {
    const d = _ADVISOR_DEFAULTS[p] ?? _ADVISOR_DEFAULTS.custom;
    modelEl.value    = d.model;
    baseUrlEl.value  = d.baseUrl;
    baseUrlRow.style.display = d.showUrl  ? "" : "none";
    apiKeyRow.style.display  = d.showKey  ? "" : "none";
  }

  function _applyVisibility(p) {
    const d = _ADVISOR_DEFAULTS[p] ?? _ADVISOR_DEFAULTS.custom;
    baseUrlRow.style.display = d.showUrl ? "" : "none";
    apiKeyRow.style.display  = d.showKey ? "" : "none";
  }

  if (!_restoreConfig()) {
    applyProviderDefaults(providerEl.value);
  } else {
    _applyVisibility(providerEl.value);
  }

  providerEl.addEventListener("change", () => applyProviderDefaults(providerEl.value));

  runBtn.addEventListener("click", async () => {
    const provider = providerEl.value;
    const model    = modelEl.value.trim()    || null;
    const baseUrl  = baseUrlEl.value.trim()  || null;
    const apiKey   = apiKeyEl.value.trim()   || null;
    _saveConfig();

    runBtn.disabled   = true;
    runBtn.textContent = t("advisorRequesting");
    resultEl.innerHTML = `<p style="font-size:12px;color:var(--muted)">${escHtml(t("advisorWaiting"))}</p>`;

    try {
      const res = await fetch("/api/advise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, model, base_url: baseUrl, api_key: apiKey }),
      });
      const data = await res.json();
      if (!res.ok || data.status === "error") {
        resultEl.innerHTML = `<p style="font-size:12px;color:#e05d44;white-space:pre-wrap">${escHtml(data.message ?? "Unknown error")}</p>`;
      } else {
        resultEl.innerHTML = `
          <div style="border-top:1px solid var(--line);padding-top:10px">
            <p style="font-size:11px;color:var(--muted);margin-bottom:6px">${escHtml(data.provider)} / ${escHtml(data.model)}</p>
            <pre style="font-size:12px;white-space:pre-wrap;line-height:1.55;margin:0">${escHtml(data.advice ?? "")}</pre>
          </div>`;
      }
    } catch (err) {
      resultEl.innerHTML = `<p style="font-size:12px;color:#e05d44">Connection error: ${escHtml(String(err))}</p>`;
    } finally {
      runBtn.disabled   = false;
      runBtn.textContent = t("advisorGetAdvice");
    }
  });
}

/* ============================================================
   Config panel
   ============================================================ */

function _initConfigPanel() {
  const _ADVISOR_KEY = "archmap.advisor.config";
  const _LANG_KEY    = "archmap.config.languages";
  const _CFG_KEY     = "archmap.config.ui";
  const _ALL_LANGS   = ["Python","JavaScript","TypeScript","Go","Rust","Java","C#","PHP","C++"];

  const providerEl   = document.getElementById("cfgProvider");
  const modelEl      = document.getElementById("cfgModel");
  const baseUrlEl    = document.getElementById("cfgBaseUrl");
  const apiKeyEl     = document.getElementById("cfgApiKey");
  const baseUrlRow   = document.getElementById("cfgBaseUrlRow");
  const apiKeyRow    = document.getElementById("cfgApiKeyRow");
  const saveBtn      = document.getElementById("cfgSaveBtn");
  const savedMsg     = document.getElementById("cfgSavedMsg");
  const langGrid     = document.getElementById("cfgLangGrid");
  const langSelect   = document.getElementById("cfgLang");
  const autoSaveEl   = document.getElementById("cfgAutoSave");
  const animationsEl = document.getElementById("cfgAnimations");
  const layoutEl     = document.getElementById("cfgLayout");
  if (!providerEl || !saveBtn) return;

  // ── Restore UI config (language, auto-save, animations, layout) ──
  let uiCfg = { lang: "en", autoSave: false, animations: true, layout: "cose" };
  try { uiCfg = { ...uiCfg, ...(JSON.parse(localStorage.getItem(_CFG_KEY)) ?? {}) }; } catch (_) {}

  _currentLang = uiCfg.lang;
  if (langSelect) langSelect.value = uiCfg.lang;
  if (autoSaveEl) autoSaveEl.checked = uiCfg.autoSave;
  if (animationsEl) animationsEl.checked = uiCfg.animations;
  if (layoutEl) layoutEl.value = uiCfg.layout;
  document.body.classList.toggle("no-animations", !uiCfg.animations);

  function _saveUiCfg() {
    try {
      localStorage.setItem(_CFG_KEY, JSON.stringify({
        lang:       _currentLang,
        autoSave:   autoSaveEl?.checked ?? false,
        animations: animationsEl?.checked ?? true,
        layout:     layoutEl?.value ?? "cose",
      }));
    } catch (_) {}
  }

  // Language selector
  if (langSelect) {
    langSelect.addEventListener("change", () => {
      _currentLang = langSelect.value;
      _saveUiCfg();
      applyI18n();
    });
  }

  // Animations toggle
  if (animationsEl) {
    animationsEl.addEventListener("change", () => {
      document.body.classList.toggle("no-animations", !animationsEl.checked);
      _saveUiCfg();
    });
  }

  // Layout selector — save immediately
  if (layoutEl) layoutEl.addEventListener("change", _saveUiCfg);

  // ── LLM provider visibility ──
  function _applyVisibility(p) {
    const d = _ADVISOR_DEFAULTS[p] ?? _ADVISOR_DEFAULTS.custom;
    baseUrlRow.style.display = d.showUrl ? "" : "none";
    apiKeyRow.style.display  = d.showKey ? "" : "none";
  }

  // Restore LLM config
  try {
    const raw = localStorage.getItem(_ADVISOR_KEY);
    if (raw) {
      const cfg = JSON.parse(raw);
      if (cfg.provider && providerEl.querySelector(`option[value="${CSS.escape(cfg.provider)}"]`))
        providerEl.value = cfg.provider;
      if (cfg.model)   modelEl.value   = cfg.model;
      if (cfg.baseUrl) baseUrlEl.value = cfg.baseUrl;
      if (cfg.apiKey)  apiKeyEl.value  = cfg.apiKey;
    } else {
      const d = _ADVISOR_DEFAULTS[providerEl.value];
      modelEl.value   = d.model;
      baseUrlEl.value = d.baseUrl;
    }
  } catch (_) {}
  _applyVisibility(providerEl.value);

  providerEl.addEventListener("change", () => {
    const d = _ADVISOR_DEFAULTS[providerEl.value] ?? _ADVISOR_DEFAULTS.custom;
    modelEl.value   = d.model;
    baseUrlEl.value = d.baseUrl;
    _applyVisibility(providerEl.value);
    if (autoSaveEl?.checked) _saveLlmCfg();
  });

  function _saveLlmCfg() {
    try {
      localStorage.setItem(_ADVISOR_KEY, JSON.stringify({
        provider: providerEl.value,
        model:    modelEl.value.trim(),
        baseUrl:  baseUrlEl.value.trim(),
        apiKey:   apiKeyEl.value.trim(),
      }));
    } catch (_) {}
  }

  // Auto-save on input when toggle is on
  [modelEl, baseUrlEl, apiKeyEl].forEach(el => {
    el?.addEventListener("input", () => { if (autoSaveEl?.checked) _saveLlmCfg(); });
  });

  // Render language checkboxes
  let savedLangs = _ALL_LANGS;
  try { savedLangs = JSON.parse(localStorage.getItem(_LANG_KEY)) ?? _ALL_LANGS; } catch (_) {}
  langGrid.innerHTML = _ALL_LANGS.map(lang =>
    `<label class="cfg-lang-check">
      <input type="checkbox" value="${lang}" ${savedLangs.includes(lang) ? "checked" : ""} />
      ${lang}
    </label>`
  ).join("");

  // Save button — persists LLM config + scan langs + UI cfg
  saveBtn.addEventListener("click", () => {
    _saveLlmCfg();
    _saveUiCfg();
    const checked = [...langGrid.querySelectorAll("input[type=checkbox]:checked")].map(cb => cb.value);
    try { localStorage.setItem(_LANG_KEY, JSON.stringify(checked)); } catch (_) {}
    savedMsg.style.display = "inline";
    setTimeout(() => { savedMsg.style.display = "none"; }, 2000);
  });
}

_initConfigPanel();
applyI18n();

/* ============================================================
   Helpers
   ============================================================ */

function heatColor(score) {
  const t = Math.min(1, Math.max(0, Number(score) || 0));
  return t <= 0.5
    ? lerp("#62b386", "#e6c25a", t / 0.5)
    : lerp("#e6c25a", "#d35266", (t - 0.5) / 0.5);
}

function lerp(a, b, t) {
  const ca = hex(a), cb = hex(b);
  return `rgb(${Math.round(ca.r+(cb.r-ca.r)*t)},${Math.round(ca.g+(cb.g-ca.g)*t)},${Math.round(ca.b+(cb.b-ca.b)*t)})`;
}

function hex(s) {
  const n = s.replace("#", "");
  return { r: parseInt(n.slice(0,2),16), g: parseInt(n.slice(2,4),16), b: parseInt(n.slice(4,6),16) };
}

function escHtml(v) {
  return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
}
