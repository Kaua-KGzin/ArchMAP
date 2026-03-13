const ROLE_COLORS = {
  controller: "#4d8be8",
  model: "#7b61ff",
  service: "#f2bf43",
  request: "#4caf70",
  database: "#ef8e2e",
  external: "#8e95a3",
  other: "#7f8ca1",
  cluster: "#5a6f8d",
};

const ROLE_LABELS = {
  controller: "Controller",
  model: "Model",
  service: "Service",
  request: "Request",
  database: "Database",
  external: "External",
  other: "Other",
  cluster: "Folder",
};

const ROLE_KEYS = ["controller", "model", "service", "request", "database", "external", "other"];

const state = {
  report: null,
  folder: "all",
  cyclesOnly: false,
  search: "",
  heatmap: false,
  clusterMode: false,
  focusDepth: 0,
  selectedNodeId: null,
  riskByFile: new Map(),
  roleFilters: {
    controller: true,
    model: true,
    service: true,
    request: true,
    database: true,
    external: true,
    other: true,
  },
};

const elements = {
  graph: document.getElementById("graph"),
  folderFilter: document.getElementById("folderFilter"),
  cyclesOnly: document.getElementById("cyclesOnly"),
  heatmapMode: document.getElementById("heatmapMode"),
  clusterMode: document.getElementById("clusterMode"),
  focusDepth: document.getElementById("focusDepth"),
  heatmapLegend: document.getElementById("heatmapLegend"),
  searchInput: document.getElementById("searchInput"),
  zoomInBtn: document.getElementById("zoomInBtn"),
  zoomOutBtn: document.getElementById("zoomOutBtn"),
  fitBtn: document.getElementById("fitBtn"),
  layoutBtn: document.getElementById("layoutBtn"),
  resetBtn: document.getElementById("resetBtn"),
  expandBtn: document.getElementById("expandBtn"),
  collapseBtn: document.getElementById("collapseBtn"),
  exportPngBtn: document.getElementById("exportPngBtn"),
  summary: document.getElementById("summary"),
  criticalList: document.getElementById("criticalList"),
  cyclesList: document.getElementById("cyclesList"),
  selectionInfo: document.getElementById("selectionInfo"),
  themeToggle: document.getElementById("themeToggle"),
  refreshBtn: document.getElementById("refreshBtn"),
  risksSummary: document.getElementById("risksSummary"),
  hotspotsList: document.getElementById("hotspotsList"),
  smellsList: document.getElementById("smellsList"),
  healthScore: document.getElementById("healthScore"),
  healthLabel: document.getElementById("healthLabel"),
  healthBreakdown: document.getElementById("healthBreakdown"),
  openProjectBtn: document.getElementById("openProjectBtn"),
  hoverCard: document.getElementById("hoverCard"),
  miniMap: document.getElementById("miniMap"),
  miniMapGraph: document.getElementById("miniMapGraph"),
  miniMapViewport: document.getElementById("miniMapViewport"),
  typeController: document.getElementById("typeController"),
  typeModel: document.getElementById("typeModel"),
  typeService: document.getElementById("typeService"),
  typeRequest: document.getElementById("typeRequest"),
  typeDatabase: document.getElementById("typeDatabase"),
  typeExternal: document.getElementById("typeExternal"),
  typeOther: document.getElementById("typeOther"),
};

const roleControlMap = {
  controller: elements.typeController,
  model: elements.typeModel,
  service: elements.typeService,
  request: elements.typeRequest,
  database: elements.typeDatabase,
  external: elements.typeExternal,
  other: elements.typeOther,
};

let cy = null;
let miniCy = null;
let controlsBound = false;

const savedTheme = localStorage.getItem("archmap-theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);

init().catch((error) => {
  elements.selectionInfo.textContent = `Failed to load graph: ${error.message}`;
});

async function init() {
  elements.refreshBtn?.classList.add("loading");
  try {
    const response = await fetch("/api/graph");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const report = await response.json();
    state.report = report;
    fillSidebar(report);
    rebuildGraph();

    if (!controlsBound) {
      bindControls();
      controlsBound = true;
    }
  } finally {
    elements.refreshBtn?.classList.remove("loading");
  }
}

function fillSidebar(report) {
  renderSummary(report.metrics, report.risks ?? {});
  renderHealth(report);
  renderCriticalFiles(report.metrics.criticalFiles ?? []);
  renderCycles(report.cycles ?? []);
  renderRisks(report);
  populateFolderFilter(report.nodes ?? []);

  state.riskByFile = new Map();
  for (const risk of report.risks?.top_risk_files ?? []) {
    state.riskByFile.set(risk.file, risk);
  }
}

function renderSummary(metrics, risks) {
  elements.summary.innerHTML = "";

  const rows = [
    `Files analyzed: <strong>${metrics.filesAnalyzed}</strong>`,
    `Dependencies: <strong>${metrics.totalDependencies}</strong>`,
    `External packages: <strong>${metrics.externalDependencies}</strong>`,
    `Circular dependencies: <strong>${metrics.circularDependencyCount}</strong>`,
    `Layer violations: <strong>${(risks.layer_violations ?? []).length}</strong>`,
    `God files: <strong>${(risks.god_modules ?? []).length}</strong>`,
    `Dependency explosions: <strong>${(risks.dependency_explosions ?? []).length}</strong>`,
  ];

  for (const text of rows) {
    const row = document.createElement("p");
    row.innerHTML = text;
    elements.summary.appendChild(row);
  }
}

function renderHealth(report) {
  const health = computeArchitectureHealth(report);

  elements.healthScore.classList.remove("good", "mid", "low");
  elements.healthScore.classList.add(health.band);
  elements.healthScore.textContent = `${health.score.toFixed(1)} / 10`;
  elements.healthLabel.textContent = `Architecture Health: ${health.label}`;

  elements.healthBreakdown.innerHTML = "";
  for (const row of health.breakdown) {
    const li = document.createElement("li");
    li.textContent = `${row.label}: ${row.value}`;
    elements.healthBreakdown.appendChild(li);
  }
}

function computeArchitectureHealth(report) {
  const metrics = report.metrics ?? {};
  const risks = report.risks ?? {};

  const cycles = Number(metrics.circularDependencyCount ?? 0);
  const layerViolations = (risks.layer_violations ?? []).length;
  const godModules = (risks.god_modules ?? []).length;
  const explosions = (risks.dependency_explosions ?? []).length;
  const complexity = metrics.complexity ?? [];
  const avgComplexity =
    complexity.length > 0
      ? complexity.reduce((acc, item) => acc + Number(item.score ?? 0), 0) / complexity.length
      : 0;

  const penalty =
    Math.min(35, cycles * 6) +
    Math.min(20, layerViolations * 4) +
    Math.min(20, godModules * 4) +
    Math.min(15, explosions * 3) +
    Math.min(10, avgComplexity * 10);

  const score = Math.max(0, 10 - penalty / 10);

  let label = "Critical";
  let band = "low";
  if (score >= 8.5) {
    label = "Healthy";
    band = "good";
  } else if (score >= 6.5) {
    label = "Attention";
    band = "mid";
  }

  return {
    score,
    label,
    band,
    breakdown: [
      { label: "Cycles", value: cycles },
      { label: "Layer violations", value: layerViolations },
      { label: "God files", value: godModules },
      { label: "Dependency explosions", value: explosions },
      { label: "Average complexity", value: `${Math.round(avgComplexity * 100)}%` },
    ],
  };
}
function renderRisks(report) {
  elements.risksSummary.innerHTML = "";
  elements.hotspotsList.innerHTML = "";
  elements.smellsList.innerHTML = "";

  const metrics = report.metrics ?? {};
  const risks = report.risks ?? {};

  const cards = [];
  const cycleCount = Number(metrics.circularDependencyCount ?? 0);
  const layerCount = (risks.layer_violations ?? []).length;
  const godCount = (risks.god_modules ?? []).length;
  const explosionCount = (risks.dependency_explosions ?? []).length;

  if (cycleCount > 0) {
    cards.push({
      level: "high",
      msg: `${cycleCount} circular dependencies detected.`,
      tip: "Break cycles with interfaces/events and clearer boundaries.",
    });
  }

  if (layerCount > 0) {
    cards.push({
      level: "high",
      msg: `${layerCount} layer violations detected.`,
      tip: "Avoid low-level modules depending on high-level layers.",
    });
  }

  if (godCount > 0) {
    cards.push({
      level: "medium",
      msg: `${godCount} god files detected.`,
      tip: "Split modules with excessive responsibilities.",
    });
  }

  if (explosionCount > 0) {
    cards.push({
      level: "medium",
      msg: `${explosionCount} dependency explosions detected.`,
      tip: "Reduce fan-in/fan-out from hotspot hubs.",
    });
  }

  if (cards.length === 0) {
    elements.risksSummary.textContent = "No architectural smells detected.";
  } else {
    for (const card of cards) {
      const div = document.createElement("div");
      div.className = `risk-item risk-${card.level}`;
      div.innerHTML = `
        <div class="risk-msg"><strong>${card.msg}</strong></div>
        <div class="risk-tip">${card.tip}</div>
      `;
      elements.risksSummary.appendChild(div);
    }
  }

  const hotspots = (risks.top_risk_files ?? []).slice(0, 8);
  if (hotspots.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No hotspot modules.";
    elements.hotspotsList.appendChild(item);
  } else {
    for (const hotspot of hotspots) {
      const item = document.createElement("li");
      const signals = (hotspot.signals ?? []).join(", ") || "none";
      item.innerHTML = `<span class="selection-code">${escapeHtml(hotspot.file)}</span> (score ${hotspot.riskScore}, ${escapeHtml(signals)})`;
      elements.hotspotsList.appendChild(item);
    }
  }

  for (const smell of [
    `Circular dependencies: ${cycleCount}`,
    `Layer violations: ${layerCount}`,
    `God files: ${godCount}`,
    `Dependency explosions: ${explosionCount}`,
  ]) {
    const item = document.createElement("li");
    item.textContent = smell;
    elements.smellsList.appendChild(item);
  }
}

function renderCriticalFiles(criticalFiles) {
  elements.criticalList.innerHTML = "";
  const top = criticalFiles.slice(0, 10);

  if (top.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No critical files detected.";
    elements.criticalList.appendChild(item);
    return;
  }

  for (const criticalFile of top) {
    const item = document.createElement("li");
    item.innerHTML = `<span class="selection-code">${escapeHtml(criticalFile.file)}</span> (${criticalFile.dependents})`;
    elements.criticalList.appendChild(item);
  }
}

function renderCycles(cycles) {
  elements.cyclesList.innerHTML = "";

  if (!cycles || cycles.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No circular dependencies found.";
    elements.cyclesList.appendChild(item);
    return;
  }

  for (const cycle of cycles.slice(0, 12)) {
    const pathText = [...cycle, cycle[0]].join(" -> ");
    const item = document.createElement("li");
    item.innerHTML = `<span class="selection-code">${escapeHtml(pathText)}</span>`;
    elements.cyclesList.appendChild(item);
  }
}

function populateFolderFilter(nodes) {
  const folders = new Set(
    nodes.filter((node) => node.type === "file").map((node) => node.folder).filter(Boolean)
  );
  const sortedFolders = [...folders].sort((a, b) => a.localeCompare(b));

  const previous = state.folder;
  elements.folderFilter.innerHTML = "";
  for (const optionValue of ["all", ...sortedFolders]) {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue === "all" ? "All folders" : optionValue;
    elements.folderFilter.appendChild(option);
  }

  if (previous === "all" || sortedFolders.includes(previous)) {
    state.folder = previous;
  } else {
    state.folder = "all";
  }
  elements.folderFilter.value = state.folder;
}

function rebuildGraph() {
  if (!state.report) {
    return;
  }

  const graphElements = buildGraphElements(state.report);

  if (cy) {
    cy.destroy();
    cy = null;
  }

  cy = cytoscape({
    container: elements.graph,
    elements: graphElements,
    wheelSensitivity: 0.2,
    style: createStylesheet(),
    layout: createLayout(),
  });

  cy.nodes().forEach((node) => {
    if (node.data("isCircular")) {
      node.addClass("circular");
    }
  });

  cy.edges().forEach((edge) => {
    if (edge.data("isCircular")) {
      edge.addClass("circular-edge");
    }
  });

  bindGraphEvents();
  initializeMiniMap(graphElements);
  applyFilters();
}

function createLayout() {
  return {
    name: "cose",
    animate: true,
    fit: true,
    padding: 38,
    idealEdgeLength: state.clusterMode ? 170 : 145,
    nodeOverlap: state.clusterMode ? 3 : 8,
  };
}

function buildGraphElements(report) {
  const graphElements = [];
  const folderClusters = new Set();

  const nodeById = new Map(report.nodes.map((node) => [node.id, node]));

  const addCluster = (folder) => {
    const clusterId = `cluster:${folder}`;
    if (folderClusters.has(clusterId)) {
      return clusterId;
    }

    folderClusters.add(clusterId);
    graphElements.push({
      data: {
        id: clusterId,
        label: folder,
        type: "cluster",
        role: "cluster",
        folder,
        nodeWidth: 180,
        nodeHeight: 110,
        outgoing: 0,
        incoming: 0,
        complexityImports: 0,
        complexityScore: 0,
        heatColor: ROLE_COLORS.cluster,
        semanticColor: ROLE_COLORS.cluster,
        isCircular: false,
      },
    });

    return clusterId;
  };

  for (const node of report.nodes) {
    const role = classifyNodeRole(node);
    const size = nodeSizeFor(node);

    const data = {
      id: node.id,
      label: node.label,
      type: node.type,
      folder: node.folder,
      language: node.language,
      role,
      semanticColor: ROLE_COLORS[role] ?? ROLE_COLORS.other,
      isCircular: Boolean(node.isCircular),
      outgoing: node.outgoing,
      incoming: node.incoming,
      complexityImports: node.complexityImports ?? 0,
      complexityScore: node.complexityScore ?? 0,
      heatColor: colorForScore(node.complexityScore ?? 0),
      nodeWidth: size.width,
      nodeHeight: size.height,
    };

    if (state.clusterMode) {
      if (node.type === "file") {
        data.parent = addCluster(node.folder || "(root)");
      } else if (node.type === "package") {
        data.parent = addCluster("(external)");
      }
    }

    graphElements.push({ data });
  }

  for (const edge of report.edges) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    const weight = edgeWeightFor(source, target);

    graphElements.push({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        isCircular: Boolean(edge.isCircular),
        edgeWidth: weight.width,
        weightBucket: weight.bucket,
      },
    });
  }

  return graphElements;
}
function bindGraphEvents() {
  cy.on("tap", "node", (event) => {
    const node = event.target;
    if (node.data("type") === "cluster") {
      return;
    }

    state.selectedNodeId = node.id();
    renderSelection(node);
    applyFilters();
  });

  cy.on("tap", (event) => {
    if (event.target === cy) {
      state.selectedNodeId = null;
      clearHighlight();
      hideHoverCard();
      elements.selectionInfo.textContent = "Click a node to inspect dependencies.";
      applyFilters();
    }
  });

  cy.on("mouseover", "node", (event) => {
    const node = event.target;
    if (node.data("type") === "cluster") {
      return;
    }
    showHoverCard(node, event.renderedPosition);
  });

  cy.on("mousemove", "node", (event) => {
    moveHoverCard(event.renderedPosition);
  });

  cy.on("mouseout", "node", () => {
    hideHoverCard();
  });

  cy.on("pan zoom resize", () => {
    syncMiniMapViewport();
  });

  cy.on("layoutstop", () => {
    syncMiniMap();
  });
}

function bindControls() {
  elements.folderFilter.addEventListener("change", () => {
    state.folder = elements.folderFilter.value;
    applyFilters();
  });

  elements.cyclesOnly.addEventListener("change", () => {
    state.cyclesOnly = elements.cyclesOnly.checked;
    applyFilters();
  });

  elements.heatmapMode.addEventListener("change", () => {
    state.heatmap = elements.heatmapMode.checked;
    applyHeatmapStyles();
  });

  elements.clusterMode.addEventListener("change", () => {
    state.clusterMode = elements.clusterMode.checked;
    rebuildGraph();
  });

  elements.focusDepth.addEventListener("change", () => {
    state.focusDepth = Number.parseInt(elements.focusDepth.value, 10) || 0;
    applyFilters();
  });

  for (const roleKey of ROLE_KEYS) {
    const checkbox = roleControlMap[roleKey];
    checkbox?.addEventListener("change", () => {
      state.roleFilters[roleKey] = checkbox.checked;
      applyFilters();
    });
  }

  elements.searchInput.addEventListener("input", () => {
    state.search = elements.searchInput.value.trim().toLowerCase();
    applyFilters();
  });

  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    focusBestSearchResult();
  });

  elements.zoomInBtn.addEventListener("click", () => {
    cy.zoom({
      level: cy.zoom() * 1.2,
      renderedPosition: {
        x: elements.graph.clientWidth / 2,
        y: elements.graph.clientHeight / 2,
      },
    });
  });

  elements.zoomOutBtn.addEventListener("click", () => {
    cy.zoom({
      level: cy.zoom() / 1.2,
      renderedPosition: {
        x: elements.graph.clientWidth / 2,
        y: elements.graph.clientHeight / 2,
      },
    });
  });

  elements.fitBtn.addEventListener("click", () => {
    cy.fit(cy.elements(":visible"), 48);
  });

  elements.layoutBtn.addEventListener("click", () => {
    cy.layout(createLayout()).run();
  });

  elements.expandBtn.addEventListener("click", () => {
    if (!state.selectedNodeId) {
      focusBestSearchResult();
    }
    state.focusDepth = Math.min(3, state.focusDepth + 1);
    elements.focusDepth.value = String(state.focusDepth);
    applyFilters();
  });

  elements.collapseBtn.addEventListener("click", () => {
    state.focusDepth = Math.max(0, state.focusDepth - 1);
    elements.focusDepth.value = String(state.focusDepth);
    applyFilters();
  });

  elements.exportPngBtn.addEventListener("click", () => {
    exportGraphPng();
  });

  elements.resetBtn.addEventListener("click", () => {
    state.selectedNodeId = null;
    state.focusDepth = 0;
    elements.focusDepth.value = "0";
    clearHighlight();
    hideHoverCard();
    elements.selectionInfo.textContent = "Click a node to inspect dependencies.";
    applyFilters();
  });

  elements.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("archmap-theme", next);
  });

  elements.refreshBtn.addEventListener("click", async () => {
    try {
      await requestReanalyze();
    } catch (error) {
      console.error("Failed to reanalyze project:", error);
    }
    await init();
  });

  elements.openProjectBtn.addEventListener("click", async () => {
    elements.openProjectBtn.classList.add("loading");
    try {
      const response = await fetch("/api/open", { method: "POST" });
      if (response.status === 200) {
        await init();
      }
    } catch (error) {
      console.error("Failed to open project:", error);
    } finally {
      elements.openProjectBtn.classList.remove("loading");
    }
  });

  elements.miniMapGraph?.addEventListener("click", onMiniMapClick);
}

async function requestReanalyze() {
  const response = await fetch("/api/reanalyze", { method: "POST" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
}

function applyFilters() {
  if (!cy) {
    return;
  }

  const visibleNodes = new Set();
  const focusSet = getFocusSet();

  cy.nodes().forEach((node) => {
    if (node.data("type") === "cluster") {
      return;
    }

    let visible = true;

    if (node.data("type") === "file") {
      if (state.folder !== "all" && node.data("folder") !== state.folder) {
        visible = false;
      }
      if (state.cyclesOnly && !node.data("isCircular")) {
        visible = false;
      }
    } else if (state.cyclesOnly && !node.data("isCircular")) {
      visible = false;
    }

    if (visible && !isRoleVisible(node.data("role"))) {
      visible = false;
    }

    if (visible && state.search) {
      const label = String(node.data("label") ?? "").toLowerCase();
      visible = matchesSearch(label, state.search);
    }

    if (visible && focusSet && !focusSet.has(node.id())) {
      visible = false;
    }

    node.scratch("_visible", visible);
  });

  if (state.clusterMode) {
    cy.nodes('[type = "cluster"]').forEach((clusterNode) => {
      const hasVisibleChildren = clusterNode.children().some((child) => child.scratch("_visible"));
      clusterNode.scratch("_visible", hasVisibleChildren);
    });
  }

  cy.nodes().forEach((node) => {
    const visible = Boolean(node.scratch("_visible"));
    node.toggleClass("hidden", !visible);
    if (visible && node.data("type") !== "cluster") {
      visibleNodes.add(node.id());
    }
  });

  cy.edges().forEach((edge) => {
    let visible = visibleNodes.has(edge.source().id()) && visibleNodes.has(edge.target().id());
    if (state.cyclesOnly && !edge.data("isCircular")) {
      visible = false;
    }
    edge.toggleClass("hidden", !visible);
  });

  applyHeatmapStyles();

  const selected = state.selectedNodeId ? cy.getElementById(state.selectedNodeId) : null;
  if (selected && selected.nonempty() && selected.visible()) {
    highlightNodePaths(selected);
  } else {
    state.selectedNodeId = null;
    clearHighlight();
  }

  syncMiniMap();
}

function getFocusSet() {
  if (state.focusDepth <= 0 || !state.selectedNodeId) {
    return null;
  }

  const selected = cy.getElementById(state.selectedNodeId);
  if (!selected || selected.empty()) {
    return null;
  }

  const keep = new Set([selected.id()]);
  const queue = [{ node: selected, level: 0 }];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || current.level >= state.focusDepth) {
      continue;
    }

    const neighbors = [
      ...current.node.outgoers("edge").targets().toArray(),
      ...current.node.incomers("edge").sources().toArray(),
    ];

    for (const neighbor of neighbors) {
      if (neighbor.data("type") === "cluster") {
        continue;
      }
      if (keep.has(neighbor.id())) {
        continue;
      }
      keep.add(neighbor.id());
      queue.push({ node: neighbor, level: current.level + 1 });
    }
  }

  return keep;
}

function highlightNodePaths(node) {
  clearHighlight();

  const visible = cy.elements(":visible");
  visible.addClass("dimmed");

  node.removeClass("dimmed").addClass("selected");

  const upstream = collectDirection(node, "upstream");
  const downstream = collectDirection(node, "downstream");

  for (const upstreamNode of upstream.nodes) {
    upstreamNode.removeClass("dimmed").addClass("upstream-node");
  }
  for (const upstreamEdge of upstream.edges) {
    upstreamEdge.removeClass("dimmed").addClass("upstream-edge");
  }

  for (const downstreamNode of downstream.nodes) {
    downstreamNode.removeClass("dimmed").addClass("downstream-node");
  }
  for (const downstreamEdge of downstream.edges) {
    downstreamEdge.removeClass("dimmed").addClass("downstream-edge");
  }
}

function collectDirection(root, direction) {
  const nodes = new Set();
  const edges = new Set();
  const visited = new Set([root.id()]);
  const queue = [{ node: root, depth: 0 }];
  const maxDepth = state.focusDepth > 0 ? state.focusDepth : 5;

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || current.depth >= maxDepth) {
      continue;
    }

    const relation =
      direction === "upstream" ? current.node.incomers("edge:visible") : current.node.outgoers("edge:visible");

    for (const edge of relation.filter("edge")) {
      const nextNode = direction === "upstream" ? edge.source() : edge.target();
      if (nextNode.id() === root.id()) {
        continue;
      }
      edges.add(edge);
      nodes.add(nextNode);

      if (visited.has(nextNode.id())) {
        continue;
      }
      visited.add(nextNode.id());
      queue.push({ node: nextNode, depth: current.depth + 1 });
    }
  }

  return { nodes, edges };
}

function clearHighlight() {
  if (!cy) {
    return;
  }
  cy.elements().removeClass("dimmed highlighted selected upstream-node downstream-node upstream-edge downstream-edge");
}
function renderSelection(node) {
  const outgoingTargets = node
    .outgoers("edge:visible")
    .targets()
    .map((target) => target.data("label"))
    .slice(0, 8);
  const incomingSources = node
    .incomers("edge:visible")
    .sources()
    .map((source) => source.data("label"))
    .slice(0, 8);

  const outgoingText = outgoingTargets.length > 0 ? outgoingTargets.join(", ") : "-";
  const incomingText = incomingSources.length > 0 ? incomingSources.join(", ") : "-";
  const complexityImports = node.data("complexityImports") ?? 0;
  const complexityScore = Math.round((node.data("complexityScore") ?? 0) * 100);
  const role = node.data("role") ?? "other";
  const risk = state.riskByFile.get(node.id());
  const riskSignals = risk?.signals?.length ? risk.signals.join(", ") : "none";
  const riskScore = risk?.riskScore ?? 0;

  const content = [
    `<p class="selection-item"><strong>File:</strong> <span class="selection-code">${escapeHtml(node.id())}</span></p>`,
    `<p class="selection-item"><strong>Type:</strong> ${escapeHtml(ROLE_LABELS[role] ?? role)}</p>`,
    `<p class="selection-item"><strong>Folder:</strong> ${escapeHtml(node.data("folder") ?? "-")}</p>`,
    `<p class="selection-item"><strong>Outbound deps:</strong> ${node.data("outgoing") ?? 0}</p>`,
    `<p class="selection-item"><strong>Inbound deps:</strong> ${node.data("incoming") ?? 0}</p>`,
    `<p class="selection-item"><strong>Complexity:</strong> ${complexityImports} imports (${complexityScore}%)</p>`,
    `<p class="selection-item"><strong>Risk score:</strong> ${riskScore}</p>`,
    `<p class="selection-item"><strong>Risk signals:</strong> ${escapeHtml(riskSignals)}</p>`,
    `<p class="selection-item"><strong>Depends on:</strong> <span class="selection-code">${escapeHtml(outgoingText)}</span></p>`,
    `<p class="selection-item"><strong>Used by:</strong> <span class="selection-code">${escapeHtml(incomingText)}</span></p>`,
  ];

  elements.selectionInfo.innerHTML = content.join("");
}

function showHoverCard(node, renderedPosition) {
  const risk = state.riskByFile.get(node.id());
  const complexity = Math.round((node.data("complexityScore") ?? 0) * 100);

  elements.hoverCard.innerHTML = `
    <p class="hover-title">${escapeHtml(node.data("label") ?? node.id())}</p>
    <p class="hover-row">File: <span class="selection-code">${escapeHtml(node.id())}</span></p>
    <p class="hover-row">Dependencies: ${node.data("outgoing") ?? 0}</p>
    <p class="hover-row">Dependents: ${node.data("incoming") ?? 0}</p>
    <p class="hover-row">Complexity: ${complexity}%</p>
    <p class="hover-row">Risk score: ${risk?.riskScore ?? 0}</p>
  `;

  elements.hoverCard.classList.remove("hidden");
  moveHoverCard(renderedPosition);
}

function moveHoverCard(renderedPosition) {
  if (!elements.hoverCard || elements.hoverCard.classList.contains("hidden")) {
    return;
  }

  const graphRect = elements.graph.getBoundingClientRect();
  const cardWidth = 250;
  const cardHeight = 136;
  let left = renderedPosition.x + 12;
  let top = renderedPosition.y + 12;

  if (left + cardWidth > graphRect.width - 8) {
    left = renderedPosition.x - cardWidth - 8;
  }
  if (top + cardHeight > graphRect.height - 8) {
    top = renderedPosition.y - cardHeight - 8;
  }

  elements.hoverCard.style.left = `${Math.max(8, left)}px`;
  elements.hoverCard.style.top = `${Math.max(8, top)}px`;
}

function hideHoverCard() {
  elements.hoverCard.classList.add("hidden");
}

function focusBestSearchResult() {
  if (!cy) {
    return;
  }

  const query = state.search.trim();
  if (!query) {
    return;
  }

  const candidates = cy
    .nodes(":visible")
    .filter((node) => node.data("type") !== "cluster")
    .map((node) => {
      const label = String(node.data("label") ?? "").toLowerCase();
      const score = label.includes(query) ? 1 + fuzzyScore(label, query) : fuzzyScore(label, query);
      return { node, score };
    })
    .filter((item) => item.score >= 0)
    .sort((a, b) => b.score - a.score);

  if (candidates.length === 0) {
    return;
  }

  const best = candidates[0].node;
  state.selectedNodeId = best.id();
  renderSelection(best);
  applyFilters();

  cy.animate({ center: { eles: best }, duration: 220 }, { queue: false });
}

function initializeMiniMap(graphElements) {
  if (miniCy) {
    miniCy.destroy();
    miniCy = null;
  }

  if (!elements.miniMapGraph) {
    return;
  }

  miniCy = cytoscape({
    container: elements.miniMapGraph,
    elements: graphElements,
    userZoomingEnabled: false,
    userPanningEnabled: false,
    boxSelectionEnabled: false,
    autolock: true,
    autoungrabify: true,
    style: [
      {
        selector: "node",
        style: {
          width: 6,
          height: 6,
          label: "",
          "background-color": "#7489a4",
          opacity: 0.9,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": "#8fa2bd",
          opacity: 0.35,
          "curve-style": "straight",
        },
      },
      {
        selector: ".hidden",
        style: {
          display: "none",
        },
      },
    ],
    layout: { name: "preset", fit: true, padding: 8 },
  });

  syncMiniMap();
}

function syncMiniMap() {
  if (!cy || !miniCy) {
    return;
  }

  miniCy.batch(() => {
    miniCy.nodes().forEach((miniNode) => {
      const mainNode = cy.getElementById(miniNode.id());
      if (!mainNode || mainNode.empty()) {
        return;
      }
      miniNode.position(mainNode.position());
      miniNode.toggleClass("hidden", mainNode.hasClass("hidden"));
    });

    miniCy.edges().forEach((miniEdge) => {
      const mainEdge = cy.getElementById(miniEdge.id());
      if (!mainEdge || mainEdge.empty()) {
        return;
      }
      miniEdge.toggleClass("hidden", mainEdge.hasClass("hidden"));
    });
  });

  miniCy.fit(miniCy.elements(":visible"), 6);
  syncMiniMapViewport();
}

function syncMiniMapViewport() {
  if (!cy || !miniCy) {
    return;
  }

  const visible = cy.elements(":visible");
  if (!visible || visible.length === 0) {
    elements.miniMapViewport.style.display = "none";
    return;
  }

  const bb = visible.boundingBox();
  if (bb.w <= 0 || bb.h <= 0) {
    elements.miniMapViewport.style.display = "none";
    return;
  }

  const extent = cy.extent();
  const miniRect = elements.miniMapGraph.getBoundingClientRect();
  const hostRect = elements.miniMap.getBoundingClientRect();

  const xRatio = clamp((extent.x1 - bb.x1) / bb.w, 0, 1);
  const yRatio = clamp((extent.y1 - bb.y1) / bb.h, 0, 1);
  const wRatio = clamp(extent.w / bb.w, 0.05, 1);
  const hRatio = clamp(extent.h / bb.h, 0.05, 1);

  const width = Math.max(12, miniRect.width * wRatio);
  const height = Math.max(12, miniRect.height * hRatio);
  const left = miniRect.left - hostRect.left + clamp(miniRect.width * xRatio, 0, miniRect.width - width);
  const top = miniRect.top - hostRect.top + clamp(miniRect.height * yRatio, 0, miniRect.height - height);

  elements.miniMapViewport.style.display = "block";
  elements.miniMapViewport.style.left = `${left}px`;
  elements.miniMapViewport.style.top = `${top}px`;
  elements.miniMapViewport.style.width = `${width}px`;
  elements.miniMapViewport.style.height = `${height}px`;
}

function onMiniMapClick(event) {
  if (!cy) {
    return;
  }

  const visible = cy.elements(":visible");
  if (!visible || visible.length === 0) {
    return;
  }

  const bb = visible.boundingBox();
  if (bb.w <= 0 || bb.h <= 0) {
    return;
  }

  const rect = elements.miniMapGraph.getBoundingClientRect();
  const ratioX = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const ratioY = clamp((event.clientY - rect.top) / rect.height, 0, 1);

  cy.animate({
    center: {
      x: bb.x1 + bb.w * ratioX,
      y: bb.y1 + bb.h * ratioY,
    },
    duration: 200,
  });
}

function exportGraphPng() {
  if (!cy) {
    return;
  }

  const pngData = cy.png({ full: true, scale: 2, bg: "#ffffff" });
  const filename = `archmap-graph-${new Date().toISOString().replaceAll(":", "-")}.png`;
  downloadDataUrl(pngData, filename);
}

function downloadDataUrl(dataUrl, filename) {
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
}
function applyHeatmapStyles() {
  cy.nodes('[type = "file"]').forEach((node) => {
    const color = state.heatmap ? node.data("heatColor") : node.data("semanticColor");
    node.style("background-color", color);
  });

  cy.nodes('[type = "package"]').forEach((node) => {
    node.style("background-color", node.data("semanticColor"));
  });

  elements.heatmapLegend.classList.toggle("legend-hidden", !state.heatmap);
}

function createStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "font-size": 11,
        "font-weight": 600,
        "text-wrap": "wrap",
        "text-max-width": 170,
        "text-background-color": "#fffdf6",
        "text-background-opacity": 0.85,
        "text-background-padding": 2,
        "text-border-color": "#d9cfbd",
        "text-border-width": 0.5,
        "text-border-opacity": 0.8,
        "border-color": "#c9c3b9",
        "border-width": 1.25,
        color: "#2f2922",
      },
    },
    {
      selector: 'node[type = "file"]',
      style: {
        shape: "round-rectangle",
        "background-color": "data(semanticColor)",
        width: "data(nodeWidth)",
        height: "data(nodeHeight)",
      },
    },
    {
      selector: 'node[type = "package"]',
      style: {
        shape: "diamond",
        "background-color": "data(semanticColor)",
        width: 30,
        height: 30,
      },
    },
    {
      selector: 'node[type = "cluster"]',
      style: {
        shape: "round-rectangle",
        "background-color": "#d8e2f0",
        "background-opacity": 0.15,
        "border-style": "dashed",
        "border-color": "#7689a8",
        "border-width": 1.1,
        padding: 16,
        color: "#60758f",
        "font-size": 10,
        "text-valign": "top",
        "text-halign": "center",
      },
    },
    {
      selector: "edge",
      style: {
        width: "data(edgeWidth)",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "#b7b2aa",
        "line-color": "#b7b2aa",
        "arrow-scale": 0.8,
      },
    },
    {
      selector: ".circular",
      style: {
        "border-color": "#cf3a3a",
      },
    },
    {
      selector: ".circular-edge",
      style: {
        "line-color": "#cf3a3a",
        "target-arrow-color": "#cf3a3a",
      },
    },
    {
      selector: ".selected",
      style: {
        "border-width": 3,
        "border-color": "#1d4ed8",
      },
    },
    {
      selector: ".upstream-node",
      style: {
        "border-width": 2.4,
        "border-color": "#2f9e63",
      },
    },
    {
      selector: ".downstream-node",
      style: {
        "border-width": 2.4,
        "border-color": "#4d8be8",
      },
    },
    {
      selector: ".upstream-edge",
      style: {
        "line-color": "#2f9e63",
        "target-arrow-color": "#2f9e63",
      },
    },
    {
      selector: ".downstream-edge",
      style: {
        "line-color": "#4d8be8",
        "target-arrow-color": "#4d8be8",
      },
    },
    {
      selector: ".dimmed",
      style: {
        opacity: 0.1,
      },
    },
    {
      selector: ".hidden",
      style: {
        display: "none",
      },
    },
  ];
}

function classifyNodeRole(node) {
  if (node.type === "package") {
    return "external";
  }

  const id = String(node.id ?? "").toLowerCase();
  const label = String(node.label ?? "").toLowerCase();

  if (id.includes("/controller") || id.includes("/controllers/") || label.includes("controller")) {
    return "controller";
  }
  if (id.includes("/model") || id.includes("/models/") || label.includes("model")) {
    return "model";
  }
  if (id.includes("/service") || id.includes("/services/") || label.includes("service")) {
    return "service";
  }
  if (id.includes("/request") || id.includes("/requests/") || label.includes("request") || label.includes("dto")) {
    return "request";
  }
  if (
    id.includes("/database/") ||
    id.includes("/db/") ||
    id.includes("/migration") ||
    id.includes("/migrations/") ||
    id.includes("repository")
  ) {
    return "database";
  }

  return "other";
}

function nodeSizeFor(node) {
  if (node.type === "package") {
    return { width: 30, height: 30 };
  }

  const dependencies = Number(node.outgoing ?? 0);
  if (dependencies > 10) {
    return { width: 82, height: 42 };
  }
  if (dependencies >= 5) {
    return { width: 62, height: 34 };
  }
  return { width: 48, height: 28 };
}

function edgeWeightFor(source, target) {
  const signal = Math.max(Number(source?.outgoing ?? 0), Number(target?.incoming ?? 0));

  if (signal > 10) {
    return { width: 3.5, bucket: "strong" };
  }
  if (signal >= 5) {
    return { width: 2.4, bucket: "medium" };
  }
  return { width: 1.2, bucket: "light" };
}

function isRoleVisible(role) {
  if (role === "cluster") {
    return true;
  }
  return Boolean(state.roleFilters[role] ?? true);
}

function matchesSearch(label, query) {
  if (label.includes(query)) {
    return true;
  }
  return fuzzyScore(label, query) >= 0.2;
}

function fuzzyScore(text, pattern) {
  if (!text || !pattern) {
    return -1;
  }

  let textIndex = 0;
  let patternIndex = 0;
  let score = 0;
  let streak = 0;

  while (textIndex < text.length && patternIndex < pattern.length) {
    if (text[textIndex] === pattern[patternIndex]) {
      patternIndex += 1;
      streak += 1;
      score += 1 + streak * 0.1;
    } else {
      streak = 0;
    }
    textIndex += 1;
  }

  if (patternIndex !== pattern.length) {
    return -1;
  }

  return score / text.length;
}

function colorForScore(score) {
  const clamped = Math.min(1, Math.max(0, Number(score) || 0));
  if (clamped <= 0.5) {
    return interpolateColor("#47b56f", "#f2bf43", clamped / 0.5);
  }
  return interpolateColor("#f2bf43", "#dd4d53", (clamped - 0.5) / 0.5);
}

function interpolateColor(startHex, endHex, ratio) {
  const start = hexToRgb(startHex);
  const end = hexToRgb(endHex);
  const t = Math.min(1, Math.max(0, ratio));

  const red = Math.round(start.r + (end.r - start.r) * t);
  const green = Math.round(start.g + (end.g - start.g) * t);
  const blue = Math.round(start.b + (end.b - start.b) * t);

  return `rgb(${red}, ${green}, ${blue})`;
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
