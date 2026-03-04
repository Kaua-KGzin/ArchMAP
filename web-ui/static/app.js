const state = {
  folder: "all",
  cyclesOnly: false,
  search: "",
};

const elements = {
  graph: document.getElementById("graph"),
  folderFilter: document.getElementById("folderFilter"),
  cyclesOnly: document.getElementById("cyclesOnly"),
  searchInput: document.getElementById("searchInput"),
  zoomInBtn: document.getElementById("zoomInBtn"),
  zoomOutBtn: document.getElementById("zoomOutBtn"),
  fitBtn: document.getElementById("fitBtn"),
  layoutBtn: document.getElementById("layoutBtn"),
  resetBtn: document.getElementById("resetBtn"),
  summary: document.getElementById("summary"),
  criticalList: document.getElementById("criticalList"),
  cyclesList: document.getElementById("cyclesList"),
  selectionInfo: document.getElementById("selectionInfo"),
};

let reportData = null;
let cy = null;

init().catch((error) => {
  elements.selectionInfo.textContent = `Failed to load graph: ${error.message}`;
});

async function init() {
  const response = await fetch("/api/graph");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  reportData = await response.json();
  fillSidebar(reportData);
  initializeGraph(reportData);
  bindControls();
}

function fillSidebar(report) {
  renderSummary(report.metrics);
  renderCriticalFiles(report.metrics.criticalFiles);
  renderCycles(report.cycles);
  populateFolderFilter(report.nodes);
}

function renderSummary(metrics) {
  elements.summary.innerHTML = "";

  const rows = [
    `Files analyzed: <strong>${metrics.filesAnalyzed}</strong>`,
    `Dependencies: <strong>${metrics.totalDependencies}</strong>`,
    `External packages: <strong>${metrics.externalDependencies}</strong>`,
    `Circular dependencies: <strong>${metrics.circularDependencyCount}</strong>`,
  ];

  rows.forEach((text) => {
    const row = document.createElement("p");
    row.innerHTML = text;
    elements.summary.appendChild(row);
  });
}

function renderCriticalFiles(criticalFiles) {
  elements.criticalList.innerHTML = "";
  const topCriticalFiles = criticalFiles.slice(0, 10);

  if (topCriticalFiles.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No critical files detected.";
    elements.criticalList.appendChild(item);
    return;
  }

  for (const criticalFile of topCriticalFiles) {
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

  const maxCyclesToRender = 12;
  const renderedCycles = cycles.slice(0, maxCyclesToRender);

  for (const cycle of renderedCycles) {
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

  const sortedFolders = [...folders].sort((left, right) => left.localeCompare(right));
  const options = ["all", ...sortedFolders];

  elements.folderFilter.innerHTML = "";
  for (const optionValue of options) {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue === "all" ? "All folders" : optionValue;
    elements.folderFilter.appendChild(option);
  }
}

function initializeGraph(report) {
  const graphElements = [
    ...report.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        folder: node.folder,
        language: node.language,
        isCircular: Boolean(node.isCircular),
        outgoing: node.outgoing,
        incoming: node.incoming,
      },
    })),
    ...report.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        isCircular: Boolean(edge.isCircular),
      },
    })),
  ];

  cy = cytoscape({
    container: elements.graph,
    elements: graphElements,
    wheelSensitivity: 0.2,
    style: createStylesheet(),
    layout: {
      name: "cose",
      animate: true,
      fit: true,
      padding: 38,
      idealEdgeLength: 140,
      nodeOverlap: 8,
    },
  });

  cy.nodes().forEach((node) => {
    if (node.data("isCircular")) {
      node.addClass("circular");
    }
  });

  cy.edges().forEach((edge) => {
    if (edge.data("isCircular")) {
      edge.addClass("circular");
    }
  });

  cy.on("tap", "node", (event) => {
    highlightNodeNeighborhood(event.target);
    renderSelection(event.target);
  });

  cy.on("tap", (event) => {
    if (event.target === cy) {
      clearHighlight();
      elements.selectionInfo.textContent = "Click a node to inspect dependencies.";
    }
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

  elements.searchInput.addEventListener("input", () => {
    state.search = elements.searchInput.value.trim().toLowerCase();
    applyFilters();
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
    cy.layout({
      name: "cose",
      animate: true,
      fit: true,
      padding: 38,
      idealEdgeLength: 140,
      nodeOverlap: 8,
    }).run();
  });

  elements.resetBtn.addEventListener("click", () => {
    clearHighlight();
    elements.selectionInfo.textContent = "Click a node to inspect dependencies.";
  });
}

function applyFilters() {
  const visibleNodes = new Set();

  cy.nodes().forEach((node) => {
    let visible = true;

    if (node.data("type") === "file") {
      if (state.folder !== "all" && node.data("folder") !== state.folder) {
        visible = false;
      }
      if (state.cyclesOnly && !node.data("isCircular")) {
        visible = false;
      }
    } else {
      visible = !state.cyclesOnly;
    }

    if (visible && state.search) {
      const label = String(node.data("label") ?? "").toLowerCase();
      visible = label.includes(state.search);
    }

    node.scratch("_visible", visible);
  });

  if (!state.cyclesOnly) {
    cy.nodes('[type = "package"]').forEach((node) => {
      const hasVisibleNeighbor = node.connectedEdges().some((edge) => {
        const sourceVisible = edge.source().scratch("_visible");
        const targetVisible = edge.target().scratch("_visible");
        return sourceVisible && targetVisible;
      });
      node.scratch("_visible", hasVisibleNeighbor);
    });
  }

  cy.nodes().forEach((node) => {
    const visible = Boolean(node.scratch("_visible"));
    node.toggleClass("hidden", !visible);
    if (visible) {
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

  clearHighlight();
  cy.fit(cy.elements(":visible"), 48);
}

function highlightNodeNeighborhood(node) {
  clearHighlight();

  const visibleElements = cy.elements(":visible");
  visibleElements.addClass("dimmed");

  const neighborhood = node.closedNeighborhood(":visible");
  neighborhood.removeClass("dimmed").addClass("highlighted");
  node.addClass("selected");
}

function clearHighlight() {
  cy.elements().removeClass("dimmed highlighted selected");
}

function renderSelection(node) {
  const outgoingTargets = node
    .outgoers("edge:visible")
    .targets()
    .map((target) => target.data("label"))
    .slice(0, 6);
  const incomingSources = node
    .incomers("edge:visible")
    .sources()
    .map((source) => source.data("label"))
    .slice(0, 6);

  const outgoingText = outgoingTargets.length > 0 ? outgoingTargets.join(", ") : "-";
  const incomingText = incomingSources.length > 0 ? incomingSources.join(", ") : "-";

  const content = [
    `<p class="selection-item"><strong>ID:</strong> <span class="selection-code">${escapeHtml(node.id())}</span></p>`,
    `<p class="selection-item"><strong>Type:</strong> ${escapeHtml(node.data("type"))}</p>`,
    `<p class="selection-item"><strong>Folder:</strong> ${escapeHtml(node.data("folder") ?? "-")}</p>`,
    `<p class="selection-item"><strong>Outgoing deps:</strong> ${node.data("outgoing") ?? 0}</p>`,
    `<p class="selection-item"><strong>Incoming deps:</strong> ${node.data("incoming") ?? 0}</p>`,
    `<p class="selection-item"><strong>Circular:</strong> ${node.data("isCircular") ? "yes" : "no"}</p>`,
    `<p class="selection-item"><strong>Depends on:</strong> <span class="selection-code">${escapeHtml(outgoingText)}</span></p>`,
    `<p class="selection-item"><strong>Used by:</strong> <span class="selection-code">${escapeHtml(incomingText)}</span></p>`,
  ];

  elements.selectionInfo.innerHTML = content.join("");
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
        "text-max-width": 160,
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
        "background-color": "#167f7f",
        width: 48,
        height: 26,
      },
    },
    {
      selector: 'node[type = "package"]',
      style: {
        shape: "diamond",
        "background-color": "#d29c27",
        width: 26,
        height: 26,
      },
    },
    {
      selector: "edge",
      style: {
        width: 1.2,
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
        "line-color": "#cf3a3a",
        "target-arrow-color": "#cf3a3a",
      },
    },
    {
      selector: ".selected",
      style: {
        "border-width": 3,
      },
    },
    {
      selector: ".highlighted",
      style: {
        opacity: 1,
      },
    },
    {
      selector: ".dimmed",
      style: {
        opacity: 0.15,
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
