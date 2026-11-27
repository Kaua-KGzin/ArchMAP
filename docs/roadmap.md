# ArchMAP Roadmap

> This file (`docs/roadmap.md`) is the single source. The root `ROADMAP.md`
> only points here.

## Next — v1.7.0 — predictable cost at scale

Implemented on the v1.7.0 branch; listed in the changelog under Unreleased:

- **Stage timings**, a fast **SCC-based impact analysis** with a 200-entry list
  cap, and faster discovery and parsing.
- **`archmap analyze --estimate`**, a progress line with an ETA, and a soft
  **`--time-budget`** / `[analysis.limits]` with visible reductions
  (`QUAL-*` findings); a 120 s default budget and a `notice` for MCP.
- A **CI perf guard** (`scripts/perf_guard.py`) and the new
  [Performance](performance.md) page.

Carried over from the v1.6.0 plan (not shipped in 1.6.0):

- **Property-based parser tests (Hypothesis)** — every language parser must
  survive arbitrary unicode input without raising.
- **GraphML and Graphviz DOT export** — for yEd, Gephi and `dot`.
- **PR report follow-ups** — base-analysis failures reported as warnings,
  `git worktree prune` before reuse, job name in the comment marker so matrix
  jobs don't share one comment.

## Next — v1.8.0

- **Incremental analysis**: re-analyze only what changed, so large projects
  stay fast on every run.
- **Termux numbers**: measured times and memory for Termux / Android on the
  [Performance](performance.md) page.
- **CI-measured baseline row**, which activates the absolute check of the perf
  guard.

## Released

### v1.6.0 (2026-11-25) — tests, bottlenecks and the PR report
- **PR report**: the GitHub Action's `comment: "true"` posts, and keeps editing, one pull-request comment with the architecture delta against the base commit: health and grade, tested-file ratio, new and resolved findings, new structural bottlenecks, lost test coverage. Threshold shifts in untouched files are listed apart. Also as `archmap diff --format markdown`.
- **Test mapping** (`testedBy`, `metrics.testMapping`, `TEST-*`) and **structural bottlenecks** (betweenness centrality, `metrics.centrality`, `GRAPH-*`).
- **`.gitignore`-aware discovery**; **findings in the JSON report** with a stable `key`.
- **Fixes and hardening**: `diff --snapshot-a/-b` on exported reports, non-root Docker image, read-only CI tokens, third-party actions pinned by SHA.

### v1.5.0 (2026-11-21) — network history and the Network exposure view
- **Network snapshots**: `netscan`/`expose --snapshot` store each scan under `.archmap/network/`; `archmap network diff|list` compares them (ports opened/closed, service/risk changes, hosts, `[network.rules]` drift), with `--fail-on-new-ports` as a CI gate.
- **`archmap memory` network section**: drift violations and notable exposed services from the latest snapshot go into the agent's session-start digest.
- **Web UI — Network exposure view**: the latest snapshot diffed against the previous one; read-only (never scans), served by a local-only endpoint.
- **Fixes**: Arch line adapter (backoff ceiling, rejected heartbeats), `serve` on read-only projects and behind `0.0.0.0`, Docker logging, `audit` skipping untracked build output, `hub-report` with null metrics.

### v1.4.2 (2026-11-02) — GitHub Action and toolchain fixes
- **GitHub Action**: installs `KG-ARCHMAP` (it installed an unrelated `archmap` PyPI package), `sarif` and `fail-on-explosions` inputs fixed, inputs passed via `env`.
- **Python 3.14** in CI and the Docker image; `express` 5.3 / `body-parser` 2.4 (GHSA-27r3-jxmh-p828); Node `>=22`.
- **Release guard**: tag/version mismatch fails the release workflows before anything is built or published.

### v1.4.1 (2026-10-21) — security and accuracy review
- Interprocedural taint analysis (`TAINT-*`) across files for Python, JS/TS, C# and Java; insecure-code checks (`CODE-*`); SARIF export for `audit`; context-aware secret ranking.
- Accuracy fixes from a field test on real repositories: precise C# `using` resolution, NestJS/Angular dotted imports, vendored code excluded from risk ranking, `--no-cache` and `--show-unresolved=all` fixed.

### v1.4.0 (2026-10-17)
- **`archmap inspect`, `hexdump`, `strings`** — static reverse engineering:
  format identification by magic bytes, ELF/PE/Mach-O/WebAssembly parsing with
  mitigations, JSON/CSV/SQLite/archive data inspection, a per-directory
  binary→library linkage graph, and `BIN-*` findings with a `--fail-on` gate.
- **`archmap audit`** — offline git-aware secret detection (`SEC-*`) and
  AI-agent configuration audit (`AGENT-*`): unpinned or insecure MCP servers,
  wildcard permissions, `curl | sh` hooks, invisible Unicode in agent
  instruction files.
- **`archmap context "<task>"`** — ranks the files to read for a task
  (identifier-aware BM25 spread over the dependency graph) within a token
  budget; also an MCP tool.
- **Analysis-quality metrics** — `metrics.analysisQuality` plus `QUAL-*`
  findings and the `--min-coverage`/`--max-parse-failures` CI gates, so files
  that fail to parse stop vanishing from the graph silently.
- **MCP server 8 → 15 tools**, **Claude Code plugin + portable agent skill**
  (`plugins/archmap/`), **`archmap commands --json`**, and **five new web UI
  views** (analysis confidence, findings, task context, inspector, audit).

### v1.3.0 (2026-08-13)
- **Unified findings model** — code-side risks (god modules, layer and custom
  rule violations, dependency explosions) and network-side findings (open
  ports, drift violations) collapse into one stable `Finding` shape with
  `id`, `domain`, `category`, `severity`, `confidence` and `evidence`, so
  `archmap memory`, the MCP tools and CI reporting treat "a problem" as one
  concept instead of three ad hoc shapes.

### v1.2.0 (2026-08-12)
- **`archmap memory`** — renders the project's already-computed architecture
  report (health score, top risk files, cycles, layer/rule violations) into
  a compact markdown digest (`.archmap/memory.md`) for AI coding agents to
  read at session start instead of re-exploring the codebase. Cache-backed
  (nearly instant on a no-op re-run) and idempotent (skips rewriting when
  nothing architectural changed). `--print` outputs the digest for a Claude
  Code `SessionStart` hook to inject straight into context; ships with
  ready-to-paste `SessionStart`/`PostToolUse` hook config.
- **`get_project_memory`** MCP tool — same digest available via `archmap mcp`
  (8 tools total). First tool an agent should call to orient itself.
- **`archmap expose` confidence scoring** — a new endpoint scanner detects
  literal host:port connection strings and config (`.env`, connection URIs)
  in the codebase; an exact match against the scanned target scores far
  higher than the previous bare service-name-to-import guess.
- **Network rules & drift detection** — `.archmap.toml` gains `[network.rules]`
  (`forbid`/`allow`, same `"source-tag -> target-tag"` syntax as
  `[architecture.rules]`). A high-confidence connection that breaks a
  declared rule is flagged as a drift violation — declared-vs-observed
  architecture extended past the codebase to the network boundary. The
  tag-matching engine behind this was extracted into a shared
  `core/analyzer/rule_engine.py` module, reused by both rule sets.

### v1.1.1 (2026-08-12)
- **`archmap expose`** — correlates `archmap netscan` results with the
  codebase's dependency graph: for each open port whose service has a known
  client library, surfaces the matching package's already-computed blast
  radius alongside the port's network-side risk rating, combined into one
  severity.
- **3 new MCP tools** — `trace_reachability`, `diff_architecture`,
  `get_network_exposure` (7 tools at the time; 8 after v1.2.0's
  `get_project_memory`).
- **MCP fixes** — the in-memory analysis cache now keys on the same content
  fingerprint the on-disk cache uses (was mtime-only, could serve stale
  results in a long-lived session after an edit); `impact_analysis` reads
  the node's precomputed `impact` field instead of recomputing it.

### v1.1.0 (2026-08-12)
- **`archmap netscan`** — nmap-style network discovery and port scanning built into ArchMAP: host discovery, threaded TCP port scanning, service fingerprinting, and per-port risk classification, all stdlib-only so it runs on Termux/Android without root. Uses a system `nmap` install automatically when present (`--no-nmap`/`--use-nmap` to override), adding OS detection (`--os-detection`) and NSE scripts (`--scripts`). First step past static-code-only analysis.
- **Web UI mobile/Termux fixes** — responsive toolbar/nav-rail layout at tablet and phone widths, and the "Open project" button now falls back to a manual path prompt instead of doing nothing when no native folder picker is available (the common case on Termux).
- **Fail-fast on a nonexistent project path** — `analyze`/`serve`/etc. now error clearly instead of silently reporting a "successful" 0-file scan, which was masking real Termux shared-storage permission issues.

### v1.0.3 (2026-06-11)
- **Tree-sitter as resilient primary parser** — per-language grammar availability + automatic per-file fallback to regex (`try_extract`) when a parse fails or is unreliable (no more dropped files).
- **Structured C# extraction** (aliases, `global using`, `static`) via typed AST nodes.
- **CI tests both the AST and regex paths** (dedicated `tree-sitter` job).

### v1.0.2 (2026-06-11)
- **Parser accuracy** — comment-aware regex fallbacks (no more phantom imports from comments) across JS/TS, Java, C#, PHP, C/C++.
- **Config-aware resolution** — Go `replace` directives, PHP composer PSR-4 autoload, Java inner classes, C# aliases + `global using`, C/C++ include-dir suffix matching.

### v1.0.1 (2026-06-11)
- **Security hardening** — `serve` binds to loopback by default; state-changing and local endpoints (`/api/project`, `/api/reanalyze`, `/api/advise`) gated to loopback; `/api/advise` validates `base_url` scheme.
- **Impact analysis O(V·E) → O(V+E)** — shared backward-adjacency map + `deque` BFS.
- **Bug fixes** — LLM advisor layer-violation field names; Mermaid label escaping.
- **tsconfig/jsconfig `paths` + `baseUrl` resolution** for JS/TS imports (improves resolution rate).
- **CI coverage gate** (`--cov-fail-under=85`); Dockerfile pinned to `python:3.13-slim`.

### v1.0.0 (2026-05-25)
- **`archmap temporal`** — temporal coupling analysis via `git log`. Detects files that change together, ranked by co-change frequency and coupling strength. `--min-commits`, `--top`, `--json` flags. Zero new deps.
- **Web UI SVG export** — "SVG" button in canvas toolbar. Scalable vector download via `cy.svg({ full: true })`. Zero new deps.
- **MCP server** (`archmap mcp`) — JSON-RPC 2.0 stdio server with 4 tools: `get_architecture_summary`, `get_file_context`, `impact_analysis`, `run_checks`. Works with Claude Code, Cursor, Windsurf.
- **Stable Public Python API** — `from archmap import analyze_project, AnalysisResult` is stable and fully typed. Zero-breaking-change commitment for all 1.x.
- **mypy strict enforcement** — 0 errors as blocking CI gate.
- **Test coverage raised to 88%** — new tests for `reachability_analyzer`, `generic_parser`, `rust_parser`, `go_parser`, `temporal_analyzer`.

### post-v0.9.0 (now in v1.0.0)
- **Per-import unresolved tracking** — `importsTotal`, `importsResolved`, `unresolvedImports` per file; `metrics.unresolvedImports` in graph report.
- **`--show-unresolved[=N]`** — list imports that failed to resolve (file + specifier).
- **Coupling budgets** — `[analysis.budgets]` in `.archmap.toml` + `--fail-on-budget-violations` CI gate + `--max-outgoing-per-file` / `--max-incoming-per-file` CLI overrides.
- **`--ignore-external`** — strip external package nodes and their edges; metrics recomputed on the filtered graph.
- **`--summary-format {text,table,markdown}`** — flexible terminal summary output.
- **SVG XSS fix** — health grade XML-escaped in `/api/badge` response.
- **Web UI** — dedicated gear-icon Config button; logo restored to Graph view navigation.

### v0.9.0
- **Parser resolution rate** — `resolutionRate` metric in all reports. CLI warns when < 70%. `--min-resolution-rate PCT` gate for CI.
- **Shell completion** — `archmap --print-completion bash|zsh|fish`. Install: `pip install "KG-ARCHMAP[completion]"`.
- **Web UI PNG export** — Download button in canvas toolbar, 2× scale, zero deps. ✅
- **Docker image** — `ghcr.io/kaua-kgzin/archmap:latest` published automatically on each release via GitHub Actions. ✅
- **i18n — 6 languages** — English, Português (Brasil), Español, Français, Deutsch, 中文 (简体). Instant switch, persisted.
- **Config panel** — Interface/General/Graph/LLM Advisor/Scan Languages. All persisted in localStorage.
- **LLM config persistence** — Provider, model, base URL, API key saved; auto-save mode.

### v0.8.1
- **`/api/badge`** — dynamic SVG health badge endpoint for README embedding (`GET /api/badge`).
- **`/api/advise`** — server-side LLM advisor endpoint; Web UI AI Advisor panel now has an interactive form with Ollama/Claude/OpenAI/custom provider support.

### v0.8.0
- **`archmap trace <entrypoint>`** — BFS reachability from any file: dependency tree by depth, coverage %, `--unreachable`, `--max-depth`.
- **`archmap advise`** — LLM-powered architectural advisor supporting Claude, OpenAI, Ollama, and any OpenAI-compatible local endpoint (LM Studio, etc.) — zero new runtime deps.
- **`archmap init --from-analysis`** — derives `.archmap.toml` layer rules from the actual dependency graph (not just directory names).
- **`archmap diff --snapshot-a/--snapshot-b`** — compare two saved JSON snapshots without git refs.
- **VS Code extension** (`vscode-extension/`) — inline diagnostics, health score status bar, trace webview, web UI launcher.
- **Web UI — Trace view**: BFS client-side with depth-colored graph highlight and coverage stats.
- **Web UI — AI Advisor view**: top issue cards and CLI command reference per provider.

### v0.7.2
- Web UI multi-view navigation: nav rail (Graph/Insights/Rules & Layers), Layer Diagram tab, Dependency Matrix tab.

### v0.7.1
- Web UI complete visual refresh (Inter + JetBrains Mono, indigo design system, health gauge, KPI tiles).
- Cytoscape bundled locally — removes CDN dependency and fixes CSP.
- CI fixes for Windows EXE build and PyPI trusted publisher.

### v0.7.0
- TypeScript parser with triple-slash reference support.
- Reusable GitHub Action (`action.yml`) with SARIF upload.
- Pre-commit hook via `archmap-check` entrypoint.
- Incremental parse cache — unchanged files skipped on re-analysis.
- `--sarif` flag for SARIF 2.1.0 export.

### v0.6.x
- Security hardening: subprocess timeouts, path traversal guards, CSP headers.
- Windows-safe CLI output and broader parser stability.
- Professional open-source governance (SECURITY.md, CODEOWNERS, py.typed).

---

## Shipped in v1.5.0 — closing the v1.3.x slice

All four items below shipped in **v1.5.0** (2026-11-21).

ArchMAP's strategic direction ("Code, Architecture & Network Intelligence")
is to correlate three domains that normally live in separate tools —
codebase structure, declared/observed architecture, and network exposure —
into one system a developer or an AI agent can query. v1.1.0–v1.2.0 built
the two hardest prerequisites for that (a real network engine, and a
code↔network correlation layer with confidence scoring); the items below
are the next slice, each buildable directly on what's already shipped.

- **Unified findings model** — ✅ Shipped in v1.3.0. Today, risks (`god_modules`, `layer_violations`,
  ...), `architecture.ruleViolations`, and `expose`'s `driftViolations` are
  three separately-shaped collections. Give every one of them a stable ID
  (`ARCH-001`, `NET-001`, ...), a `severity`, a `confidence` (already exists
  for expose findings, missing everywhere else), and an `evidence` list, so
  `archmap memory`, the MCP tools, and CI reporting can treat "a problem" as
  one concept instead of three ad hoc shapes. Purely a reshaping of data
  ArchMAP already computes — no new detectors required.
- **`archmap memory` network section** — ✅ Done. When the project has a
  stored network snapshot, `archmap memory` folds its `driftViolations` and
  notable findings (risky port, `high`/`critical` severity, confidence
  ≥ 0.7, or a `[network.rules]` violation) into the digest, so an AI agent's
  session-start context includes network exposure without a separate MCP
  call. `--no-network` opts out.
- **Network observation snapshots + diff** — ✅ Done. `archmap netscan` and
  `archmap expose` accept `--snapshot`, storing the report under
  `.archmap/network/`; `archmap network diff` compares two of them (ports
  opened/closed, service and risk changes, hosts appearing/disappearing,
  drift violations new/resolved), and `archmap network list` shows the
  history. `--fail-on-new-ports` turns it into a CI gate.
- **Declared vs. observed, surfaced in the web UI** — ✅ Done. The code side
  (`[architecture.rules]` → `ARCH-*`) has been in the **Findings** view since
  v1.4.0. The network side now has its own **Network exposure** view: it
  reads the latest `--snapshot` (so `archmap serve` still never scans), lists
  `NET-*` findings and `[network.rules]` drift, and diffs against the
  previous snapshot. It is served by a local-only `POST /api/network`.

---

## Shipped in v1.4.0 — agent-native ArchMAP

Most of this slice is done and released; the items still marked open below
carry over into the next one.

Derived from the [October 2026 market-trends research](research/market-trends-2026-10.md):
GitHub's monthly trending list is dominated by tooling for AI coding agents
(skills/plugins, persistent memory, context-window economy, verified security
findings). ArchMAP already has the deterministic engine those tools lack; the
items below close the distribution and ergonomics gap.

- **Agent plugin + skill** — ✅ Done. `plugins/archmap/` (Claude Code plugin:
  MCP server, `SessionStart` memory hook, `archmap` skill) and a root
  `.claude-plugin/marketplace.json`; the same `SKILL.md` installs into other
  agents via `npx skills add`. See [AI agent plugin](agents.md).
- **Task-scoped context retrieval** — ✅ Done (`archmap context`, `get_relevant_context`). MCP tool `get_relevant_context(task,
  budget_tokens)`: BM25 (stdlib `sqlite3` FTS5) over paths/symbols/imports,
  re-ranked by graph proximity and risk, returning the minimal file set for a
  task within a token budget.
- **Snapshot history + observations** — persist each analysis under
  `.archmap/history/` (generalizing the network-snapshot item above) and
  derive trend observations ("risk rising 5 runs in a row", "cycle open for
  40 days") for `archmap memory`.
- **`archmap recon` + verified findings** — partially done: `archmap inspect` maps binaries, mitigations, and linkage; still open: deterministic attack-surface map
  (entrypoints, network-facing code, blast radius) for agentic security
  audits; `Finding.status` (`confirmed`/`needs_validation`/`rejected`) and a
  published JSON Schema.
- **`archmap agents audit`** — ✅ Done as `archmap audit` (`AGENT-*`). `AGENT-*` findings for risky agent config
  (`.mcp.json`, hooks, permissions): `curl | sh` hooks, wildcard permissions,
  plaintext secrets, non-loopback `http://` MCP servers.
- **Secret exposure findings** — ✅ Done as `archmap audit` (`SEC-*`, git-aware). `SEC-*` findings from the existing
  endpoint scanner's `.env`/config pass (offline, conservative).
- **`archmap commands --json`** — ✅ Done. machine-readable command catalog for
  agent-native CLI discovery.

- **Analysis-quality metrics** — ✅ Done (`metrics.analysisQuality`, `QUAL-*`, `--min-coverage`, `--max-parse-failures`).
- **Static reverse engineering** — ✅ Done (`archmap inspect`, `hexdump`, `strings`; ELF/PE/Mach-O/WASM, data and archives, binary linkage graph).

### Next reverse-engineering steps

- **Go build info and Rust `cargo-auditable` metadata** — module versions
  embedded in binaries become package nodes, so `impact_analysis` works on a
  binary's dependencies (and pairs with vulnerability databases).
- **DEX/APK depth** — decode the binary `AndroidManifest.xml` (permissions,
  exported components) and DEX class/method tables.
- **ELF/PE symbol-level call graph** — PLT/IAT cross-references from code
  sections, without a full disassembler.
- **Binary nodes in the unified graph** — feed `inspect` linkage graphs into
  the same node/edge model as code and network (the Unified System Graph).

---

## Longer-term

- **Unified System Graph** — extend the dependency graph's node/edge model
  (currently `file`/`package` nodes with import edges) with network-side
  node types (`host`, `port`, `service`) and typed edges (`CONNECTS_TO`,
  `EXPOSES`), so a high-confidence `expose` match becomes a real edge in the
  same graph structure `impact_analysis`/`trace_reachability` already
  traverse — "what's the blast radius of this Postgres instance" answered
  by the same BFS as "what's the blast radius of this file," instead of a
  bolted-on correlation step. The largest, most structural item here;
  `core/exposure/correlate.py`'s confidence-scored matching is the
  proof-of-concept this would formalize into the graph itself.
- **Recommendation engine / refactor planner** — turn a finding (god module,
  boundary violation, network drift) into a concrete, ordered remediation
  plan (`archmap refactor-plan <finding-id>`), building on the unified
  findings model above.
- **Infrastructure criticality scoring** — combine a network node's
  dependency count, centrality, and change frequency (once network
  snapshots exist) into a single criticality score, the network-side
  counterpart to the existing risk score for files.
- Plugin SDK for custom parsers and analyzers via entry points.
- Multi-repo topology support.
- WebSocket-based live UI refresh.
- **Mutation testing (mutmut)** — Apply mutation testing to core analysis modules (`cycle_detector.py`, `risk_analyzer.py`, `complexity_analyzer.py`).
- **Homebrew formula** — Distribute as a Homebrew tap for macOS users (`brew install kaua-kgzin/tap/archmap`).
- **Web UI accessibility (a11y)** — Audit and fix WCAG 2.1 AA compliance: color contrast, keyboard navigation, focus management, ARIA labels for the Cytoscape.js graph.
- **API stability policy** — Publish a formal versioning contract: public vs. internal modules, deprecation timeline.

---

## Continuous

These are ongoing commitments rather than versioned deliverables. They run in parallel with every release cycle.

- **Supply chain audit** — `pip-audit` runs in CI on every push (implemented in v0.8.x). Dependabot watches Python deps, npm deps, GitHub Actions pins (SHA-pinned, including `action.yml`) and the Docker base image on a weekly schedule. No manual audit cadence required.
- **Architectural self-check (dogfooding)** — CI runs `archmap analyze src/archmap/ --fail-on-cycles` on every push. ArchMAP must pass its own analysis. A `--min-health` threshold is not enforced in CI yet; adding one, and raising it as the codebase improves, is the next step for this gate.
- **mypy coverage expansion** — mypy is a blocking CI step (`check_untyped_defs`, `warn_unused_ignores`). Type annotations are added to every new or modified file; `--strict` on the full `src/archmap/` tree remains the goal.
- **Documentation freshness** — Every CLI flag, JSON output field, and `.archmap.toml` key introduced in a PR must be documented in the same PR. The MkDocs build runs with `--strict` in CI; broken references fail the docs workflow.
- **Parser parity** — As new language features are introduced (e.g., Python 3.12+ type parameter syntax, TypeScript 5.x satisfies operator), parser regression tests are added before the parser update is merged. No silent parser regressions.
