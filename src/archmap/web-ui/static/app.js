const FILE_COLOR  = "#6173e0";
const PKG_COLOR   = "#62b386";
const CYCLE_COLOR = "#d35266";
const EDGE_COLOR  = "#c4cad5";

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
      el.selectionInfo.innerHTML = `<p class="selection-muted">Click a node to inspect dependencies.</p>`;
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
  el.layoutBtn.addEventListener("click", () => cy.layout({ name: "cose", animate: true, fit: true, padding: 60, idealEdgeLength: 110, nodeRepulsion: 9000 }).run());
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
  document.getElementById("navBtnGraph")?.addEventListener("click",    () => switchLeftView("graph"));
  document.getElementById("navBtnInsights")?.addEventListener("click", () => switchLeftView("insights"));
  document.getElementById("navBtnRules")?.addEventListener("click",    () => switchLeftView("rules"));

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
  `;
}

/* ============================================================
   Navigation — left panel views
   ============================================================ */

const LP_NAV = { graph: ["lpGraph","navBtnGraph"], insights: ["lpInsights","navBtnInsights"], rules: ["lpRules","navBtnRules"] };

function switchLeftView(key) {
  for (const [k, [viewId, btnId]] of Object.entries(LP_NAV)) {
    document.getElementById(viewId)?.classList.toggle("lp-hidden", k !== key);
    document.getElementById(btnId)?.classList.toggle("rail-btn-active", k === key);
  }
  if (key === "insights" && reportData) renderInsights(reportData);
  if (key === "rules"    && reportData) renderRules(reportData);
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
    { label: "Health score",         val: `${score}/100` },
    { label: "Files analysed",       val: m.filesAnalyzed ?? 0 },
    { label: "Total dependencies",   val: m.totalDependencies ?? 0 },
    { label: "Circular dependencies",val: m.circularDependencyCount ?? 0 },
    { label: "External packages",    val: m.externalDependencies ?? 0 },
    { label: "Rule violations",      val: m.architectureRuleViolations ?? 0 },
    { label: "Avg complexity",       val: `${((m.complexity?.avgComplexityScore ?? 0) * 100).toFixed(1)}%` },
    { label: "Critical files",       val: (m.criticalFiles ?? []).length },
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
          Architecture layers
        </div>
        <div class="rule-card-body">No layer rules configured. Add an <code>.archmap.toml</code> file to define your architecture layers and dependency rules.</div>
      </div>
      <div class="rule-card" style="margin-top:0">
        <div class="rule-card-head">
          <svg viewBox="0 0 24 24"><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>
          Violations
        </div>
        <div class="rule-card-body">${viols > 0 ? `${viols} rule violation${viols !== 1 ? "s" : ""} detected.` : "No violations detected."}</div>
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
