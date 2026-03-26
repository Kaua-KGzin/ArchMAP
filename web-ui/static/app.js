import {
  LANGUAGE_ORDER,
  ROLE_LABEL_KEYS,
  STORAGE_KEYS,
  THEME_ORDER,
  normalizeLanguage,
  translate,
} from "./i18n.js";

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

const ROLE_KEYS = ["controller", "model", "service", "request", "database", "external", "other"];
const RELATION_PREVIEW_LIMIT = 8;

const state = {
  report: null,
  history: null,
  historyView: { kind: "idle", message: "" },
  folder: "all",
  cyclesOnly: false,
  search: "",
  heatmap: false,
  clusterMode: false,
  focusDepth: 0,
  selectedNodeId: null,
  language: readStoredLanguage(),
  theme: readStoredTheme(),
  currentProjectPath: ".",
  pinnedProjectPath: readStoredPinnedProject(),
  riskByFile: new Map(),
  nodeById: new Map(),
  edges: [],
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
  storyInfo: document.getElementById("storyInfo"),
  rulesList: document.getElementById("rulesList"),
  criticalList: document.getElementById("criticalList"),
  cyclesList: document.getElementById("cyclesList"),
  historyStatus: document.getElementById("historyStatus"),
  historyTrend: document.getElementById("historyTrend"),
  historyTimeline: document.getElementById("historyTimeline"),
  historyCycles: document.getElementById("historyCycles"),
  historyHotspots: document.getElementById("historyHotspots"),
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
  pinProjectQuickBtn: document.getElementById("pinProjectQuickBtn"),
  pinProjectBtn: document.getElementById("pinProjectBtn"),
  openPinnedBtn: document.getElementById("openPinnedBtn"),
  currentProjectPath: document.getElementById("currentProjectPath"),
  pinnedProjectPath: document.getElementById("pinnedProjectPath"),
  projectStatus: document.getElementById("projectStatus"),
  pinnedStatus: document.getElementById("pinnedStatus"),
  languageSelect: document.getElementById("languageSelect"),
  openFileBtn: document.getElementById("openFileBtn"),
  drillModuleBtn: document.getElementById("drillModuleBtn"),
  projectViewBtn: document.getElementById("projectViewBtn"),
  themeSelect: document.getElementById("themeSelect"),
  toolbarKicker: document.getElementById("toolbarKicker"),
  selectionActionHint: document.getElementById("selectionActionHint"),
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

applyTheme(state.theme, { persist: false });
applyLanguage(state.language, { persist: false, rerender: false });

init().catch((error) => {
  elements.selectionInfo.textContent = t("messages.failedLoadGraph", { message: error.message });
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
    if (state.selectedNodeId && state.nodeById.has(state.selectedNodeId)) {
      selectNodeById(state.selectedNodeId, { center: false });
    } else {
      state.selectedNodeId = null;
      resetSelectionView();
    }

    if (!controlsBound) {
      bindControls();
      controlsBound = true;
    }

    await refreshProjectState();
    document.body.dataset.ready = "true";
    void loadHistory();
  } finally {
    elements.refreshBtn?.classList.remove("loading");
  }
}

function t(key, vars = {}) {
  return translate(state.language, key, vars);
}

function roleLabel(role) {
  const key = ROLE_LABEL_KEYS[role];
  return key ? t(key) : role;
}

function readStoredLanguage() {
  try {
    return normalizeLanguage(localStorage.getItem(STORAGE_KEYS.language) || navigator.language || "en");
  } catch {
    return normalizeLanguage(navigator.language || "en");
  }
}

function persistLanguage(language) {
  try {
    localStorage.setItem(STORAGE_KEYS.language, language);
  } catch {
    return;
  }
}

function readStoredPinnedProject() {
  try {
    return String(localStorage.getItem(STORAGE_KEYS.pinnedProject) || "").trim();
  } catch {
    return "";
  }
}

function persistPinnedProject(path) {
  try {
    if (path) {
      localStorage.setItem(STORAGE_KEYS.pinnedProject, path);
    } else {
      localStorage.removeItem(STORAGE_KEYS.pinnedProject);
    }
  } catch {
    return;
  }
}

function normalizeTheme(theme) {
  const value = String(theme || "").trim().toLowerCase();
  if (value === "paper") {
    return "light";
  }
  if (value === "midnight") {
    return "dark";
  }
  return THEME_ORDER.includes(value) ? value : "dark";
}

function readStoredTheme() {
  try {
    return normalizeTheme(localStorage.getItem(STORAGE_KEYS.theme) || "dark");
  } catch {
    return "dark";
  }
}

function persistTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEYS.theme, theme);
  } catch {
    return;
  }
}

function applyTheme(theme, options = {}) {
  state.theme = normalizeTheme(theme);
  document.documentElement.setAttribute("data-theme", state.theme);
  if (elements.themeSelect) {
    populateThemeOptions();
    elements.themeSelect.value = state.theme;
  }
  updateThemeButtonState();
  if (options.persist !== false) {
    persistTheme(state.theme);
  }
}

function applyLanguage(language, options = {}) {
  state.language = normalizeLanguage(language);
  document.documentElement.lang = state.language;
  populateLanguageOptions();
  populateThemeOptions();
  applyStaticTranslations();
  updateThemeButtonState();
  syncPinnedProjectUi();
  if (options.persist !== false) {
    persistLanguage(state.language);
  }
  if (options.rerender !== false && state.report) {
    rerenderLocalizedPanels();
  }
}

function populateLanguageOptions() {
  if (!elements.languageSelect) {
    return;
  }

  elements.languageSelect.innerHTML = "";
  for (const language of LANGUAGE_ORDER) {
    const option = document.createElement("option");
    option.value = language;
    option.textContent = t(`language.${language}`);
    elements.languageSelect.appendChild(option);
  }
  elements.languageSelect.value = state.language;
}

function populateThemeOptions() {
  if (!elements.themeSelect) {
    return;
  }

  elements.themeSelect.innerHTML = "";
  for (const theme of THEME_ORDER) {
    const option = document.createElement("option");
    option.value = theme;
    option.textContent = t(`theme.${theme}`);
    elements.themeSelect.appendChild(option);
  }
  elements.themeSelect.value = state.theme;
}

function applyStaticTranslations() {
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  }
  for (const node of document.querySelectorAll("[data-i18n-title]")) {
    node.setAttribute("title", t(node.dataset.i18nTitle));
  }
  for (const node of document.querySelectorAll("[data-i18n-aria-label]")) {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  }
}

async function refreshProjectState() {
  state.currentProjectPath = await fetchCurrentProjectPath();
  syncPinnedProjectUi();
}

function getCurrentProjectName() {
  const normalized = String(state.currentProjectPath || "").replaceAll("\\", "/");
  const segments = normalized.split("/").filter(Boolean);
  return segments.at(-1) || t("project.kickerFallback");
}

function syncPinnedProjectUi() {
  const pinnedPath = String(state.pinnedProjectPath || "").trim();
  const currentPath = String(state.currentProjectPath || ".").trim() || ".";
  const isPinned = pinnedPath && pinnedPath === currentPath;

  if (elements.currentProjectPath) {
    elements.currentProjectPath.textContent = currentPath;
  }
  if (elements.pinnedProjectPath) {
    elements.pinnedProjectPath.textContent = pinnedPath || t("project.noPinned");
  }
  if (elements.toolbarKicker) {
    elements.toolbarKicker.textContent = getCurrentProjectName();
  }
  if (elements.projectStatus) {
    elements.projectStatus.textContent = isPinned
      ? t("project.statusPinned")
      : pinnedPath
        ? t("project.statusSaved")
        : t("project.statusUnpinned");
  }
  if (elements.pinnedStatus) {
    elements.pinnedStatus.textContent = isPinned
      ? t("project.badgePinned")
      : pinnedPath
        ? t("project.badgeSaved")
        : t("project.badgeEmpty");
    elements.pinnedStatus.className = `history-pill ${isPinned ? "history-pill-ok" : ""}`.trim();
  }
  if (elements.pinProjectBtn) {
    elements.pinProjectBtn.textContent = isPinned ? t("actions.unpinProject") : t("actions.pinProject");
  }
  if (elements.openPinnedBtn) {
    elements.openPinnedBtn.disabled = !pinnedPath || pinnedPath === currentPath;
  }
  if (elements.pinProjectQuickBtn) {
    elements.pinProjectQuickBtn.classList.toggle("rail-btn-active", Boolean(isPinned));
    elements.pinProjectQuickBtn.setAttribute(
      "title",
      isPinned ? t("nav.unpinProjectTitle") : t("nav.pinProjectTitle")
    );
    elements.pinProjectQuickBtn.setAttribute(
      "aria-label",
      isPinned ? t("nav.unpinProjectTitle") : t("nav.pinProjectTitle")
    );
  }
}

function togglePinnedProject() {
  const currentPath = String(state.currentProjectPath || ".").trim() || ".";
  if (state.pinnedProjectPath === currentPath) {
    state.pinnedProjectPath = "";
  } else {
    state.pinnedProjectPath = currentPath;
  }
  persistPinnedProject(state.pinnedProjectPath);
  syncPinnedProjectUi();
}

async function openPinnedProject() {
  const pinnedPath = String(state.pinnedProjectPath || "").trim();
  if (!pinnedPath || pinnedPath === state.currentProjectPath) {
    return false;
  }

  const response = await fetch("/api/project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: pinnedPath }),
  });
  if (!response.ok) {
    const payload = await readJsonSafely(response);
    throw new Error(payload?.message ?? `HTTP ${response.status}`);
  }
  return true;
}

function updateThemeButtonState() {
  if (!elements.themeToggle) {
    return;
  }
  elements.themeToggle.setAttribute("title", `${t("nav.themeTitle")} (${t(`theme.${state.theme}`)})`);
  elements.themeToggle.setAttribute("aria-label", `${t("nav.themeTitle")} (${t(`theme.${state.theme}`)})`);
}

function cycleTheme() {
  const currentIndex = THEME_ORDER.indexOf(state.theme);
  const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % THEME_ORDER.length;
  applyTheme(THEME_ORDER[nextIndex]);
}

function rerenderLocalizedPanels() {
  if (!state.report) {
    return;
  }

  renderSummary(state.report.metrics ?? {}, state.report.risks ?? {});
  renderHealth(state.report);
  renderStory(state.report, state.history);
  renderCriticalFiles(state.report.metrics?.criticalFiles ?? []);
  renderCycles(state.report.cycles ?? []);
  renderRisks(state.report);
  populateFolderFilter(state.report.nodes ?? []);

  if (state.historyView.kind === "ready" && state.history) {
    renderHistory(state.history);
  } else if (state.historyView.kind === "unavailable") {
    renderHistoryUnavailable(state.historyView.message);
  } else {
    renderHistoryLoading();
  }

  const selectedNode = getSelectedNode();
  if (selectedNode) {
    renderSelection(selectedNode);
  } else {
    resetSelectionView();
  }
}

function fillSidebar(report) {
  state.history = null;
  state.nodeById = new Map((report.nodes ?? []).map((node) => [node.id, node]));
  state.edges = report.edges ?? [];
  renderSummary(report.metrics, report.risks ?? {});
  renderHealth(report);
  renderStory(report, null);
  renderHistoryLoading();
  renderCriticalFiles(report.metrics.criticalFiles ?? []);
  renderCycles(report.cycles ?? []);
  renderRisks(report);
  populateFolderFilter(report.nodes ?? []);

  state.riskByFile = new Map();
  for (const risk of report.risks?.top_risk_files ?? []) {
    state.riskByFile.set(risk.file, risk);
  }
}

function resetSelectionView(message = t("selection.defaultMessage")) {
  elements.selectionInfo.textContent = message;
  updateSelectionActions(null);
}

function getReportNode(nodeId) {
  return state.nodeById.get(nodeId) ?? null;
}

function getGraphNode(nodeId) {
  if (!cy || !nodeId) {
    return null;
  }

  const node = cy.getElementById(nodeId);
  return node && node.nonempty() ? node : null;
}

function getSelectedNode() {
  return getGraphNode(state.selectedNodeId);
}

function getRelatedNodes(nodeId, direction) {
  if (!nodeId) {
    return [];
  }

  const relatedIds = new Set();
  const results = [];

  for (const edge of state.edges) {
    const isMatch =
      direction === "outgoing" ? edge.source === nodeId : edge.target === nodeId;
    if (!isMatch) {
      continue;
    }

    const relatedId = direction === "outgoing" ? edge.target : edge.source;
    if (relatedIds.has(relatedId)) {
      continue;
    }

    const relatedNode = getReportNode(relatedId);
    if (!relatedNode) {
      continue;
    }

    relatedIds.add(relatedId);
    results.push(relatedNode);
  }

  return results;
}

function renderNodeChips(nodes, emptyMessage) {
  if (!nodes.length) {
    return `<span class="selection-empty">${escapeHtml(emptyMessage)}</span>`;
  }

  const visibleNodes = nodes.slice(0, RELATION_PREVIEW_LIMIT);
  const chips = visibleNodes.map(
    (node) => `
      <button class="selection-chip" type="button" data-node-id="${escapeHtml(node.id)}">
        ${escapeHtml(node.label ?? node.id)}
      </button>
    `
  );

  if (nodes.length > visibleNodes.length) {
    chips.push(`<span class="selection-overflow">+${nodes.length - visibleNodes.length}</span>`);
  }

  return chips.join("");
}

function renderFolderChip(folder) {
  if (!folder) {
    return `<span class="selection-empty">${escapeHtml(t("selection.noModuleFolder"))}</span>`;
  }

  return `
    <button class="selection-chip selection-chip-accent" type="button" data-folder="${escapeHtml(folder)}">
      ${escapeHtml(folder)}
    </button>
  `;
}

function renderSummary(metrics, risks) {
  elements.summary.innerHTML = "";
  const averageInstability = Math.round(
    Number(metrics.coupling?.averageInstability ?? 0) * 100
  );

  const rows = [
    `${t("summary.files")}: <strong>${metrics.filesAnalyzed}</strong>`,
    `${t("summary.dependencies")}: <strong>${metrics.totalDependencies}</strong>`,
    `${t("summary.externalPackages")}: <strong>${metrics.externalDependencies}</strong>`,
    `${t("summary.circularDependencies")}: <strong>${metrics.circularDependencyCount}</strong>`,
    `${t("summary.averageInstability")}: <strong>${averageInstability}%</strong>`,
    `${t("summary.detectedStyle")}: <strong>${escapeHtml(metrics.architectureStyle ?? t("common.unknown"))}</strong>`,
    `${t("summary.layerViolations")}: <strong>${(risks.layer_violations ?? []).length}</strong>`,
    `${t("summary.godFiles")}: <strong>${(risks.god_modules ?? []).length}</strong>`,
    `${t("summary.dependencyExplosions")}: <strong>${(risks.dependency_explosions ?? []).length}</strong>`,
  ];

  for (const text of rows) {
    const row = document.createElement("p");
    row.innerHTML = text;
    elements.summary.appendChild(row);
  }
}

function renderStory(report, history) {
  const architecture = report.architecture ?? {};
  const health = architecture.health ?? {};
  const style = architecture.detectedStyle ?? {};
  const rules = architecture.activeRules ?? { forbid: [], allow: [] };
  const ruleViolations = architecture.ruleViolations ?? [];
  const historyTrend = history?.trend ?? null;

  const storyLines = [
    t("story.currentStyle", { style: escapeHtml(style.name ?? t("common.unknown")) }),
    escapeHtml(health.summary ?? t("story.summaryUnavailable")),
  ];

  if (historyTrend) {
    storyLines.push(
      t("story.historyTrend", {
        count: history.windowSize,
        health: signed(Number(historyTrend.healthDelta ?? 0)),
        cycles: signed(Number(historyTrend.cycleDelta ?? 0)),
      })
    );
  } else {
    storyLines.push(t("story.historyLoading"));
  }

  if (ruleViolations.length > 0) {
    storyLines.push(t("story.ruleViolations", { count: ruleViolations.length }));
  } else if ((rules.forbid?.length ?? 0) + (rules.allow?.length ?? 0) > 0) {
    storyLines.push(t("story.rulesHolding"));
  }

  elements.storyInfo.innerHTML = storyLines
    .map((line) => `<p class="story-line">${line}</p>`)
    .join("");

  elements.rulesList.innerHTML = "";
  const configuredRules = [
    ...(rules.forbid ?? []).map((rule) => ({ kind: "forbid", rule })),
    ...(rules.allow ?? []).map((rule) => ({ kind: "allow", rule })),
  ];
  if (!configuredRules.length) {
    const item = document.createElement("li");
    item.textContent = t("story.noRules");
    elements.rulesList.appendChild(item);
    return;
  }

  for (const entry of configuredRules.slice(0, 6)) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="story-badge story-badge-${entry.kind}">
        ${entry.kind === "forbid" ? t("story.forbid") : t("story.allow")}
      </span>
      <span class="selection-code">${escapeHtml(entry.rule)}</span>
    `;
    elements.rulesList.appendChild(item);
  }
}

function renderHistoryLoading() {
  state.historyView = { kind: "loading", message: "" };
  elements.historyStatus.textContent = t("history.loading");
  elements.historyStatus.className = "history-pill";
  elements.historyTrend.innerHTML = `<p class="selection-muted">${escapeHtml(
    t("history.collecting")
  )}</p>`;
  elements.historyTimeline.innerHTML = "";
  elements.historyCycles.innerHTML = "";
  elements.historyHotspots.innerHTML = "";
}

function renderHistoryUnavailable(message) {
  state.historyView = { kind: "unavailable", message };
  elements.historyStatus.textContent = t("history.unavailable");
  elements.historyStatus.className = "history-pill history-pill-warn";
  elements.historyTrend.innerHTML = `<p class="selection-muted">${escapeHtml(message)}</p>`;
  elements.historyTimeline.innerHTML = "";
  elements.historyCycles.innerHTML = "";
  elements.historyHotspots.innerHTML = "";
}

function renderHistory(history) {
  state.historyView = { kind: "ready", message: "" };
  const trend = history?.trend ?? {};
  const snapshots = history?.snapshots ?? [];
  const cycles = history?.cycles ?? [];
  const hotspots = history?.hotspots ?? [];

  elements.historyStatus.textContent = t("history.commits", { count: history?.windowSize ?? 0 });
  elements.historyStatus.className = "history-pill history-pill-ok";
  elements.historyTrend.innerHTML = `
    <div class="history-stat-grid">
      <div class="history-stat-card">
        <span class="history-stat-label">${escapeHtml(t("history.health"))}</span>
        <strong class="${deltaClass(Number(trend.healthDelta ?? 0), true)}">${signed(
          Number(trend.healthDelta ?? 0)
        )}</strong>
      </div>
      <div class="history-stat-card">
        <span class="history-stat-label">${escapeHtml(t("history.cycles"))}</span>
        <strong class="${deltaClass(Number(trend.cycleDelta ?? 0), false)}">${signed(
          Number(trend.cycleDelta ?? 0)
        )}</strong>
      </div>
      <div class="history-stat-card">
        <span class="history-stat-label">${escapeHtml(t("history.instability"))}</span>
        <strong class="${deltaClass(Number(trend.instabilityDeltaPercent ?? 0), false)}">${signedFloat(
          Number(trend.instabilityDeltaPercent ?? 0)
        )}%</strong>
      </div>
    </div>
    <p class="history-note">${escapeHtml(t("history.note"))}</p>
  `;

  elements.historyTimeline.innerHTML = "";
  for (const snapshot of snapshots.slice().reverse()) {
    const item = document.createElement("li");
    item.className = "timeline-item";
    item.innerHTML = `
      <div class="timeline-marker"></div>
      <div class="timeline-content">
        <div class="timeline-topline">
          <span class="selection-code">${escapeHtml(snapshot.shortCommit ?? "")}</span>
          <span class="timeline-health">${snapshot.health}/100</span>
        </div>
        <p class="timeline-title">${escapeHtml(snapshot.subject ?? t("history.noCommitSubject"))}</p>
        <p class="timeline-meta">
          ${escapeHtml(
            t("history.timelineMeta", {
              dependencies: snapshot.dependencies,
              cycles: snapshot.cycles,
              rules: snapshot.ruleViolations,
            })
          )}
        </p>
      </div>
    `;
    elements.historyTimeline.appendChild(item);
  }

  renderHistoryList(
    elements.historyCycles,
    cycles.slice(0, 4).map((item) => ({
      label: `${item.cycle.join(" -> ")} - ${t("history.since", {
        commit: item.introducedIn?.shortCommit ?? "?",
      })}`,
      meta: item.suspectedOwner
        ? t("history.lastTouched", {
          author: item.suspectedOwner.author,
          file: item.suspectedOwner.file,
        })
        : t("history.noAuthorData"),
      nodeId: item.cycle[0],
    })),
    t("history.noCyclesWindow")
  );

  renderHistoryList(
    elements.historyHotspots,
    hotspots.slice(0, 4).map((item) => ({
      label: `${item.file} - ${t("history.score", { score: item.riskScore })}`,
      meta: item.lastTouched
        ? `${item.lastTouched.author} [${item.lastTouched.shortCommit}]`
        : t("history.noAuthorData"),
      nodeId: item.file,
    })),
    t("history.noHotspotBlame")
  );
}

function renderHistoryList(container, items, emptyMessage) {
  container.innerHTML = "";
  if (!items.length) {
    const item = document.createElement("li");
    item.textContent = emptyMessage;
    container.appendChild(item);
    return;
  }

  for (const entry of items) {
    const item = document.createElement("li");
    item.innerHTML = `
      <button class="nav-list-btn nav-list-btn-compact" type="button" data-node-id="${escapeHtml(
        entry.nodeId
      )}">
        <span>${escapeHtml(entry.label)}</span>
        <span class="nav-list-meta">${escapeHtml(entry.meta)}</span>
      </button>
    `;
    container.appendChild(item);
  }
}

function renderHealth(report) {
  const health = computeArchitectureHealth(report);

  elements.healthScore.classList.remove("good", "mid", "low");
  elements.healthScore.classList.add(health.band);
  elements.healthScore.textContent = `${health.score.toFixed(1)} / 10`;
  elements.healthLabel.textContent = t("health.label", { label: health.label });

  elements.healthBreakdown.innerHTML = "";
  for (const row of health.breakdown) {
    const li = document.createElement("li");
    li.textContent = `${row.label}: ${row.value}`;
    elements.healthBreakdown.appendChild(li);
  }
}

function computeArchitectureHealth(report) {
  const architectureHealth = report.architecture?.health;
  if (architectureHealth && Number.isFinite(Number(architectureHealth.score))) {
    const score = Number(architectureHealth.score) / 10;
    let band = "low";
    if (score >= 8.5) {
      band = "good";
    } else if (score >= 6.5) {
      band = "mid";
    }

    return {
      score,
      label: architectureHealth.grade ?? t("health.unknown"),
      band,
      breakdown: [
        {
          label: t("health.breakdown.style"),
          value: report.architecture?.detectedStyle?.name ?? t("common.unknown"),
        },
        {
          label: t("health.breakdown.layers"),
          value: (report.architecture?.detectedLayers ?? []).join(", ") || t("health.none"),
        },
        {
          label: t("health.breakdown.customRules"),
          value: (report.architecture?.ruleViolations ?? []).length,
        },
        {
          label: t("health.breakdown.drivers"),
          value:
            (architectureHealth.drivers ?? []).slice(0, 2).join(" | ") ||
            t("health.noMajorPenalties"),
        },
      ],
    };
  }

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

  let label = t("health.critical");
  let band = "low";
  if (score >= 8.5) {
    label = t("health.healthy");
    band = "good";
  } else if (score >= 6.5) {
    label = t("health.attention");
    band = "mid";
  }

  return {
    score,
    label,
    band,
    breakdown: [
      { label: t("health.breakdown.cycles"), value: cycles },
      { label: t("health.breakdown.layerViolations"), value: layerViolations },
      { label: t("health.breakdown.godFiles"), value: godModules },
      { label: t("health.breakdown.dependencyExplosions"), value: explosions },
      { label: t("health.breakdown.averageComplexity"), value: `${Math.round(avgComplexity * 100)}%` },
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
  const customRuleCount = (report.architecture?.ruleViolations ?? []).length;

  if (cycleCount > 0) {
    cards.push({
      level: "high",
      msg: `${cycleCount} ${t("summary.circularDependencies").toLowerCase()}.`,
      tip: t("risks.cycleTip"),
    });
  }

  if (layerCount > 0) {
    cards.push({
      level: "high",
      msg: `${layerCount} ${t("summary.layerViolations").toLowerCase()}.`,
      tip: t("risks.layerTip"),
    });
  }

  if (godCount > 0) {
    cards.push({
      level: "medium",
      msg: `${godCount} ${t("summary.godFiles").toLowerCase()}.`,
      tip: t("risks.godTip"),
    });
  }

  if (explosionCount > 0) {
    cards.push({
      level: "medium",
      msg: `${explosionCount} ${t("summary.dependencyExplosions").toLowerCase()}.`,
      tip: t("risks.explosionTip"),
    });
  }

  if (customRuleCount > 0) {
    cards.push({
      level: "high",
      msg: `${customRuleCount} ${t("health.breakdown.customRules").toLowerCase()}.`,
      tip: t("risks.customTip"),
    });
  }

  if (cards.length === 0) {
    elements.risksSummary.textContent = t("risks.noneDetected");
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
    item.textContent = t("risks.hotspotsNone");
    elements.hotspotsList.appendChild(item);
  } else {
    for (const hotspot of hotspots) {
      const item = document.createElement("li");
      const signals = (hotspot.signals ?? []).join(", ") || t("common.none");
      item.innerHTML = `
        <button class="nav-list-btn" type="button" data-node-id="${escapeHtml(hotspot.file)}">
          <span class="selection-code">${escapeHtml(hotspot.file)}</span>
          <span class="nav-list-meta">${escapeHtml(t("history.score", { score: hotspot.riskScore }))}, ${escapeHtml(signals)}</span>
        </button>
      `;
      elements.hotspotsList.appendChild(item);
    }
  }

  for (const smell of [
    `${t("summary.circularDependencies")}: ${cycleCount}`,
    `${t("summary.layerViolations")}: ${layerCount}`,
    `${t("summary.godFiles")}: ${godCount}`,
    `${t("summary.dependencyExplosions")}: ${explosionCount}`,
    `${t("health.breakdown.customRules")}: ${customRuleCount}`,
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
    item.textContent = t("critical.none");
    elements.criticalList.appendChild(item);
    return;
  }

  for (const criticalFile of top) {
    const item = document.createElement("li");
    item.innerHTML = `
      <button class="nav-list-btn" type="button" data-node-id="${escapeHtml(criticalFile.file)}">
        <span class="selection-code">${escapeHtml(criticalFile.file)}</span>
        <span class="nav-list-meta">${escapeHtml(
          t("critical.dependents", { count: criticalFile.dependents })
        )}</span>
      </button>
    `;
    elements.criticalList.appendChild(item);
  }
}

function renderCycles(cycles) {
  elements.cyclesList.innerHTML = "";

  if (!cycles || cycles.length === 0) {
    const item = document.createElement("li");
    item.textContent = t("cycles.none");
    elements.cyclesList.appendChild(item);
    return;
  }

  for (const [index, cycle] of cycles.slice(0, 12).entries()) {
    const pathText = [...cycle, cycle[0]].join(" -> ");
    const item = document.createElement("li");
    item.innerHTML = `
      <button class="nav-list-btn" type="button" data-cycle-index="${index}">
        <span class="selection-code">${escapeHtml(pathText)}</span>
      </button>
    `;
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
    option.textContent = optionValue === "all" ? t("common.allFolders") : optionValue;
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
      efferentCoupling: node.efferentCoupling ?? node.outgoing ?? 0,
      afferentCoupling: node.afferentCoupling ?? node.incoming ?? 0,
      instability: node.instability ?? 0,
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

    selectNodeById(node.id(), { center: false });
  });

  cy.on("tap", (event) => {
    if (event.target === cy) {
      state.selectedNodeId = null;
      clearHighlight();
      hideHoverCard();
      resetSelectionView();
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
    resetSelectionView();
    applyFilters();
  });

  elements.themeToggle.addEventListener("click", () => {
    cycleTheme();
  });

  elements.themeSelect?.addEventListener("change", () => {
    applyTheme(elements.themeSelect.value);
  });

  elements.languageSelect?.addEventListener("change", () => {
    applyLanguage(elements.languageSelect.value);
  });

  elements.pinProjectQuickBtn?.addEventListener("click", () => {
    togglePinnedProject();
  });

  elements.pinProjectBtn?.addEventListener("click", () => {
    togglePinnedProject();
  });

  elements.openPinnedBtn?.addEventListener("click", async () => {
    elements.openPinnedBtn.classList.add("loading");
    try {
      const changed = await openPinnedProject();
      if (changed) {
        await init();
      }
    } catch (error) {
      console.error("Failed to open pinned project:", error);
      elements.selectionInfo.textContent = t("messages.failedOpenProject", {
        message: error.message,
      });
    } finally {
      elements.openPinnedBtn.classList.remove("loading");
    }
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
      const changed = await requestOpenProject();
      if (changed) {
        await init();
      }
    } catch (error) {
      console.error("Failed to open project:", error);
      elements.selectionInfo.textContent = t("messages.failedOpenProject", {
        message: error.message,
      });
    } finally {
      elements.openProjectBtn.classList.remove("loading");
    }
  });

  elements.openFileBtn?.addEventListener("click", async () => {
    const node = getSelectedNode();
    if (!node || node.data("type") !== "file") {
      return;
    }

    elements.openFileBtn.classList.add("loading");
    try {
      await requestOpenFile(node.id());
    } catch (error) {
      console.error("Failed to open file:", error);
      elements.selectionInfo.innerHTML = `
        <p class="selection-item selection-error">
          ${escapeHtml(t("messages.failedOpenFile", { message: error.message }))}
        </p>
      `;
      updateSelectionActions(node);
    } finally {
      elements.openFileBtn.classList.remove("loading");
    }
  });

  elements.drillModuleBtn?.addEventListener("click", () => {
    const node = getSelectedNode();
    if (!node) {
      return;
    }
    drillIntoFolder(node.data("folder"), { nodeId: node.id() });
  });

  elements.projectViewBtn?.addEventListener("click", () => {
    resetProjectView();
  });

  for (const interactiveElement of [
    elements.selectionInfo,
    elements.criticalList,
    elements.hotspotsList,
    elements.cyclesList,
    elements.historyCycles,
    elements.historyHotspots,
  ]) {
    interactiveElement?.addEventListener("click", handleNavigationInteraction);
  }

  elements.miniMapGraph?.addEventListener("click", onMiniMapClick);
}

async function requestReanalyze() {
  const response = await fetch("/api/reanalyze", { method: "POST" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
}

async function requestOpenProject() {
  const response = await fetch("/api/open", { method: "POST" });
  const payload = await readJsonSafely(response);
  if (response.ok) {
    return true;
  }
  if (response.status === 204) {
    return false;
  }
  if ([404, 405, 501].includes(response.status) || payload?.mode === "manual_path") {
    return requestManualProjectPath(payload?.message);
  }

  throw new Error(payload?.message ?? `HTTP ${response.status}`);
}

async function requestManualProjectPath(reasonMessage = "") {
  const currentPath = await fetchCurrentProjectPath();
  const promptMessage = reasonMessage
    ? t("messages.promptProjectPathWithReason", { reason: reasonMessage })
    : t("messages.promptProjectPath");
  const nextPath = window.prompt(promptMessage, currentPath);
  const normalizedPath = String(nextPath ?? "").trim();

  if (!normalizedPath || normalizedPath === currentPath) {
    return false;
  }

  const response = await fetch("/api/project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: normalizedPath }),
  });
  if (!response.ok) {
    const payload = await readJsonSafely(response);
    throw new Error(payload?.message ?? `HTTP ${response.status}`);
  }

  return true;
}

async function requestOpenFile(nodeId) {
  const response = await fetch("/api/open-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nodeId }),
  });
  const payload = await readJsonSafely(response);
  if (!response.ok) {
    throw new Error(payload?.message ?? `HTTP ${response.status}`);
  }
  return payload;
}

async function loadHistory(limit = 12) {
  try {
    const response = await fetch(`/api/history?limit=${encodeURIComponent(limit)}`);
    const payload = await readJsonSafely(response);
    if (!response.ok) {
      if ([404, 405, 501].includes(response.status)) {
        renderHistoryUnavailable(
          payload?.message ?? t("history.noHistoryRuntime")
        );
        renderStory(state.report, null);
        return;
      }
      throw new Error(payload?.message ?? `HTTP ${response.status}`);
    }

    state.history = payload;
    renderStory(state.report, payload);
    renderHistory(payload);
  } catch (error) {
    console.error("Failed to load history:", error);
    renderHistoryUnavailable(error.message);
    renderStory(state.report, null);
  }
}

async function fetchCurrentProjectPath() {
  const response = await fetch("/api/project");
  if (!response.ok) {
    return ".";
  }

  const payload = await readJsonSafely(response);
  return String(payload?.path ?? ".").trim() || ".";
}

async function readJsonSafely(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function deltaClass(value, positiveIsGood = false) {
  if (value === 0) {
    return "delta-flat";
  }
  const positive = value > 0;
  if ((positive && positiveIsGood) || (!positive && !positiveIsGood)) {
    return "delta-good";
  }
  return "delta-bad";
}

function handleNavigationInteraction(event) {
  const nodeTrigger = event.target.closest("[data-node-id]");
  if (nodeTrigger?.dataset.nodeId) {
    selectNodeById(nodeTrigger.dataset.nodeId);
    return;
  }

  const folderTrigger = event.target.closest("[data-folder]");
  if (folderTrigger?.dataset.folder) {
    drillIntoFolder(folderTrigger.dataset.folder, { nodeId: state.selectedNodeId });
    return;
  }

  const cycleTrigger = event.target.closest("[data-cycle-index]");
  if (cycleTrigger?.dataset.cycleIndex) {
    const cycleIndex = Number.parseInt(cycleTrigger.dataset.cycleIndex, 10);
    if (Number.isFinite(cycleIndex)) {
      focusCycle(cycleIndex);
    }
  }
}

function syncFilterControls() {
  elements.folderFilter.value = state.folder;
  elements.focusDepth.value = String(state.focusDepth);
  elements.cyclesOnly.checked = state.cyclesOnly;
  elements.searchInput.value = state.search;
}

function ensureNodeVisibleContext(node) {
  const role = node.data("role");
  const folder = node.data("folder");
  const label = String(node.data("label") ?? "").toLowerCase();
  const nodeId = String(node.id()).toLowerCase();

  if (roleControlMap[role] && !roleControlMap[role].checked) {
    roleControlMap[role].checked = true;
    state.roleFilters[role] = true;
  }

  if (state.cyclesOnly && !node.data("isCircular")) {
    state.cyclesOnly = false;
  }

  if (state.folder !== "all" && folder && state.folder !== folder) {
    state.folder = folder;
  }

  if (state.search && !label.includes(state.search) && !nodeId.includes(state.search)) {
    state.search = "";
  }

  syncFilterControls();
}

function selectNodeById(nodeId, options = {}) {
  const node = getGraphNode(nodeId);
  if (!node || node.data("type") === "cluster") {
    return;
  }

  ensureNodeVisibleContext(node);
  state.selectedNodeId = node.id();
  applyFilters();

  const selectedNode = getSelectedNode();
  if (!selectedNode) {
    return;
  }

  renderSelection(selectedNode);
  if (options.center === false) {
    return;
  }

  focusNodeSet(options.fitNodeIds ?? [selectedNode.id()]);
}

function focusNodeSet(nodeIds) {
  if (!cy || !Array.isArray(nodeIds) || nodeIds.length === 0) {
    return;
  }

  let collection = cy.collection();
  for (const nodeId of nodeIds) {
    const node = getGraphNode(nodeId);
    if (!node || !node.visible()) {
      continue;
    }
    collection = collection.add(node);
  }

  if (collection.length === 0) {
    return;
  }

  cy.animate(
    {
      fit: {
        eles: collection,
        padding: 80,
      },
      duration: 240,
    },
    { queue: false }
  );
}

function drillIntoFolder(folder, options = {}) {
  if (!folder) {
    return;
  }

  state.folder = folder;
  state.search = "";
  state.cyclesOnly = false;
  syncFilterControls();
  applyFilters();

  if (options.nodeId) {
    selectNodeById(options.nodeId, { center: options.center });
  } else {
    updateSelectionActions(getSelectedNode());
    focusNodeSet(
      (state.report?.nodes ?? [])
        .filter((node) => node.type === "file" && node.folder === folder)
        .map((node) => node.id)
    );
  }
}

function resetProjectView() {
  state.folder = "all";
  state.focusDepth = 0;
  state.cyclesOnly = false;
  state.search = "";
  syncFilterControls();
  applyFilters();

  const selectedNode = getSelectedNode();
  if (selectedNode) {
    renderSelection(selectedNode);
  } else {
    resetSelectionView();
  }

  const visibleNodeIds = cy ? cy.nodes(":visible").map((node) => node.id()) : [];
  focusNodeSet(visibleNodeIds);
}

function focusCycle(cycleIndex) {
  const cycles = state.report?.cycles ?? [];
  const cycle = cycles[cycleIndex];
  if (!Array.isArray(cycle) || cycle.length === 0) {
    return;
  }

  state.folder = "all";
  state.search = "";
  state.cyclesOnly = false;
  state.focusDepth = Math.max(2, state.focusDepth);
  syncFilterControls();
  applyFilters();
  selectNodeById(cycle[0], { fitNodeIds: cycle });
}

function updateSelectionActions(node) {
  const folder = node?.data("folder") ?? "";
  const canOpenFile = Boolean(node && node.data("type") === "file");
  const hasProjectViewContext =
    state.folder !== "all" || state.focusDepth > 0 || state.cyclesOnly || Boolean(state.search);

  if (elements.openFileBtn) {
    elements.openFileBtn.disabled = !canOpenFile;
    elements.openFileBtn.title = canOpenFile
      ? t("selection.openHintReady")
      : t("selection.openHintDisabled");
  }
  if (elements.drillModuleBtn) {
    elements.drillModuleBtn.disabled = !folder;
    elements.drillModuleBtn.title = folder
      ? t("selection.drillHintReady", { folder })
      : t("selection.drillHintDisabled");
  }
  if (elements.projectViewBtn) {
    elements.projectViewBtn.disabled = !hasProjectViewContext;
    elements.projectViewBtn.title = hasProjectViewContext
      ? t("selection.resetHintReady")
      : t("selection.resetHintDisabled");
  }
  if (elements.selectionActionHint) {
    elements.selectionActionHint.textContent = [
      canOpenFile ? t("selection.openHintReady") : t("selection.openHintDisabled"),
      folder ? t("selection.drillHintReady", { folder }) : t("selection.drillHintDisabled"),
      hasProjectViewContext ? t("selection.resetHintReady") : t("selection.resetHintDisabled"),
    ].join(" ");
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
    updateSelectionActions(selected);
  } else {
    const hadSelection = Boolean(state.selectedNodeId);
    state.selectedNodeId = null;
    clearHighlight();
    updateSelectionActions(null);
    if (hadSelection) {
      resetSelectionView();
    }
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
  const outgoingNodes = getRelatedNodes(node.id(), "outgoing");
  const incomingNodes = getRelatedNodes(node.id(), "incoming");
  const complexityImports = node.data("complexityImports") ?? 0;
  const complexityScore = Math.round((node.data("complexityScore") ?? 0) * 100);
  const role = node.data("role") ?? "other";
  const risk = state.riskByFile.get(node.id());
  const riskSignals = risk?.signals?.length ? risk.signals.join(", ") : t("common.none");
  const riskScore = risk?.riskScore ?? 0;
  const language = node.data("language") ?? t("common.unknown");
  const folder = node.data("folder") ?? "";
  const efferentCoupling = node.data("efferentCoupling") ?? node.data("outgoing") ?? 0;
  const afferentCoupling = node.data("afferentCoupling") ?? node.data("incoming") ?? 0;
  const instability = Number(node.data("instability") ?? 0);
  const instabilityPercent = Math.round(instability * 100);

  const content = [
    `<p class="selection-item"><strong>${escapeHtml(t("selection.file"))}:</strong> <span class="selection-code">${escapeHtml(node.id())}</span></p>`,
    `<div class="selection-stats-grid">`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.type"))}:</strong> ${escapeHtml(
      roleLabel(role)
    )}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.language"))}:</strong> ${escapeHtml(language)}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.outbound"))}:</strong> ${node.data("outgoing") ?? 0}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.inbound"))}:</strong> ${node.data("incoming") ?? 0}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.complexity"))}:</strong> ${complexityImports} ${escapeHtml(
      t("selection.importsWord")
    )} (${complexityScore}%)</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.riskScore"))}:</strong> ${riskScore}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.efferent"))}:</strong> ${efferentCoupling}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.afferent"))}:</strong> ${afferentCoupling}</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.instability"))}:</strong> ${instabilityPercent}%</p>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.interpretation"))}:</strong> ${escapeHtml(
      describeInstability(instability, afferentCoupling, efferentCoupling)
    )}</p>`,
    `</div>`,
    `<p class="selection-item"><strong>${escapeHtml(t("selection.riskSignals"))}:</strong> ${escapeHtml(riskSignals)}</p>`,
    `<div class="selection-section">`,
    `<p class="selection-section-title">${escapeHtml(t("selection.module"))}</p>`,
    `<div class="selection-chip-group">${renderFolderChip(folder)}</div>`,
    `</div>`,
    `<div class="selection-section">`,
    `<p class="selection-section-title">${escapeHtml(t("selection.dependsOn"))}</p>`,
    `<div class="selection-chip-group">${renderNodeChips(
      outgoingNodes,
      t("selection.noDependencies")
    )}</div>`,
    `</div>`,
    `<div class="selection-section">`,
    `<p class="selection-section-title">${escapeHtml(t("selection.usedBy"))}</p>`,
    `<div class="selection-chip-group">${renderNodeChips(
      incomingNodes,
      t("selection.noDependents")
    )}</div>`,
    `</div>`,
  ];

  elements.selectionInfo.innerHTML = content.join("");
  updateSelectionActions(node);
}

function showHoverCard(node, renderedPosition) {
  const risk = state.riskByFile.get(node.id());
  const complexity = Math.round((node.data("complexityScore") ?? 0) * 100);

  elements.hoverCard.innerHTML = `
    <p class="hover-title">${escapeHtml(node.data("label") ?? node.id())}</p>
    <p class="hover-row">${escapeHtml(t("hover.file"))}: <span class="selection-code">${escapeHtml(
      node.id()
    )}</span></p>
    <p class="hover-row">${escapeHtml(t("hover.dependencies"))}: ${node.data("outgoing") ?? 0}</p>
    <p class="hover-row">${escapeHtml(t("hover.dependents"))}: ${node.data("incoming") ?? 0}</p>
    <p class="hover-row">${escapeHtml(t("hover.complexity"))}: ${complexity}%</p>
    <p class="hover-row">${escapeHtml(t("hover.riskScore"))}: ${risk?.riskScore ?? 0}</p>
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
  selectNodeById(best.id());
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

function describeInstability(instability, afferentCoupling, efferentCoupling) {
  if (afferentCoupling === 0 && efferentCoupling === 0) {
    return t("instability.isolated");
  }
  if (instability >= 0.75) {
    return t("instability.high");
  }
  if (instability <= 0.25) {
    return t("instability.stable");
  }
  return t("instability.balanced");
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

function signed(value) {
  const parsed = Math.trunc(Number(value) || 0);
  return `${parsed >= 0 ? "+" : ""}${parsed}`;
}

function signedFloat(value) {
  const parsed = Number(value) || 0;
  return `${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}`;
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
