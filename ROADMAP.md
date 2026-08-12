# ArchMAP Roadmap

## Released

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
- **Shell completion** — `archmap --print-completion bash|zsh|fish`. Install: `pip install archmap[completion]`.
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

## Medium-term (v1.0.0)

- **Public Python API** — Define and document a stable programmatic surface (`from archmap import analyze_project, ArchMapConfig, AnalysisResult`). Add `__all__` to public modules, document with MkDocs examples, establish a deprecation policy (`DeprecationWarning` + semver). Unlocks IDE plugins, pytest integrations, and custom CI tooling beyond the CLI.
- **mypy enforcement (blocking)** — Graduate mypy from non-blocking (infrastructure only, v0.8.x) to a hard CI gate. Expand typed coverage module by module until `--strict` is feasible on the full `src/archmap/` tree.
- **Version bump to v1.0.0** — Finalize the public API contract, write a migration guide from 0.x, and tag the first stable release.

---

## Longer-term

- Plugin SDK for custom parsers and analyzers via entry points.
- Change coupling detector via `git log` analysis.
- Multi-repo topology support.
- WebSocket-based live UI refresh.
- GraphML and Graphviz DOT export formats.
- **Tree-sitter based parsers** — ✅ Done. Optional `[tree-sitter]` extra ships AST-based parsers for all 9 languages; regex fallback preserved when the extra is not installed.
- **Property-based testing (Hypothesis)** — Add `hypothesis` to dev deps and use it on all language parsers. The parser must never crash on any valid unicode input.
- **Mutation testing (mutmut)** — Apply mutation testing to core analysis modules (`cycle_detector.py`, `risk_analyzer.py`, `complexity_analyzer.py`).
- **Homebrew formula** — Distribute as a Homebrew tap for macOS users (`brew install kaua-kgzin/tap/archmap`).
- **Web UI accessibility (a11y)** — Audit and fix WCAG 2.1 AA compliance: color contrast, keyboard navigation, focus management, ARIA labels for the Cytoscape.js graph.
- **SVG export** — Add a "Download SVG" button using Cytoscape.js's `cy.svg()` API.
- **API stability policy** — Publish a formal versioning contract: public vs. internal modules, deprecation timeline.

---

## Continuous

These are ongoing commitments rather than versioned deliverables. They run in parallel with every release cycle.

- **Supply chain audit** — `pip-audit` runs in CI on every push (implemented in v0.8.x). Dependabot watches Python deps, npm deps, and GitHub Actions pins on a weekly schedule. No manual audit cadence required.
- **Architectural self-check (dogfooding)** — CI runs `archmap analyze src/archmap/ --fail-on-cycles` on every push. ArchMAP must pass its own analysis. The health score threshold (`--min-health`) is raised incrementally as the codebase improves, making the gate self-tightening.
- **mypy coverage expansion** — Type annotations are added incrementally to every new or modified file. The mypy CI step starts non-blocking (infrastructure, v0.8.x) and transitions to a hard gate (v0.9.x) once baseline coverage is established. No new untyped functions merged after v0.9.0.
- **Documentation freshness** — Every CLI flag, JSON output field, and `.archmap.toml` key introduced in a PR must be documented in the same PR. The MkDocs build runs with `--strict` in CI; broken references fail the docs workflow.
- **Parser parity** — As new language features are introduced (e.g., Python 3.12+ type parameter syntax, TypeScript 5.x satisfies operator), parser regression tests are added before the parser update is merged. No silent parser regressions.
