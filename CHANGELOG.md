# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- **`archmap netscan`** — nmap-style network discovery and port scanning, built
  stdlib-only so it runs without root on Termux (Android) as well as on regular
  Linux/macOS/Windows. Accepts single hosts, CIDR blocks, or dash ranges;
  supports host discovery (ping with TCP-probe fallback), threaded TCP port
  scanning, service banner fingerprinting, and JSON output. `--use-nmap`
  delegates to a system `nmap` install for deeper scans (`-sV`, `-O`, etc. via
  `--nmap-args`). First step toward ArchMAP mapping more than just source code.
- **`archmap netscan` report redesign** — human-readable output is now a clean
  aligned table (PORT/STATE/SERVICE/INFO per host, plus an up/duration summary
  line and a totals footer) instead of a flat list, so it reads the same way
  regardless of engine. New `--os-detection` flag surfaces nmap's `-O` OS guess
  when the nmap engine runs; nmap's own scan stats, version, and richer service
  info (product/version/extrainfo) are now parsed and shown too.
- **nmap is now the default `netscan` engine when installed** — it's simply a
  more capable scanner than a from-scratch one. `--use-nmap` now only forces
  it (erroring if missing) instead of opting in; pass `--no-nmap` to fall back
  to the built-in stdlib-only scanner even when nmap is present.
- **Per-port analysis** — every open port is now checked against a static
  table of known-risky ports/services (Telnet, SMB, RDP, VNC, exposed
  Redis/MongoDB/Elasticsearch/Memcached, unauthenticated Docker API, etc.)
  and flagged with a `[LEVEL RISK]` tag and reason in the report, on either
  engine. The Python engine's fingerprinting now does a real HTTP(S) `GET`
  (including over TLS on 443/8443/...) to extract the page title and
  `Server` header instead of just the first response line. New `--scripts`
  flag runs nmap's default NSE scripts + version detection (`-sC -sV`) for
  deeper per-port and per-host analysis (page titles, TLS cert info, known
  misconfigurations); script and risk info are parsed into the JSON report
  and shown indented under each port in the human-readable output, with a
  risky-port count added to the summary footer.

### Fixed
- **Web UI (`archmap serve`) mobile/Termux layout** — the desktop toolbar
  (fixed-width search box, spacer-pushed buttons) no longer gets squeezed
  into an unreadable single row once the workspace collapses to its
  single-column mobile layout (≤960px, e.g. tablets and phones in
  landscape). The toolbar now wraps into title/tabs/search/action rows,
  export/refresh buttons go icon-only with accessible labels, the nav rail
  scrolls horizontally with larger touch targets instead of overflowing
  off-screen, and the mini-map shrinks (then hides below 460px) instead of
  overlapping graph content. Verified at common phone/tablet/landscape
  viewport sizes.

## [1.0.3] - 2026-06-11

Tree-sitter engine overhaul. Tree-sitter becomes a resilient *primary* parser
with automatic per-file fallback to the regex path. Fully backward-compatible;
the optional `[tree-sitter]` extra is still optional.

### Added
- **Per-language grammar availability** — each tree-sitter grammar now loads
  independently. A single missing or broken grammar (e.g. `tree-sitter-php`) no
  longer disables tree-sitter for every other language; the affected language
  simply uses its regex fallback. New `ts_engine.language_available(name)`.
- **Automatic per-file fallback (`ts_engine.try_extract`)** — the parsers call a
  single orchestrator that returns the structured tree-sitter result, or `None`
  to request the regex fallback when tree-sitter cannot be trusted for that file:
  the grammar is unavailable, parsing/querying raised an exception, or the parse
  contained syntax errors *and* recovered no imports. Previously a file that made
  tree-sitter raise was dropped from the graph entirely.
- **Structured C# extraction** — `using` directives are read from typed AST
  nodes, so `using Alias = Real.Namespace;` resolves to the real namespace
  (not the alias), and `global using` / `using static` are handled. This matches
  the regex fallback's behaviour so both paths agree.
- **CI now tests both paths** — a dedicated `tree-sitter` job runs the suite with
  the AST grammars installed, while the existing `quality` job continues to
  cover the regex fallback. The tree-sitter code path was previously untested in
  CI.

### Changed
- Rust regex fallback now strips comments before matching, consistent with the
  other regex fallbacks introduced in 1.0.2.
- `ts_engine` extractors were refactored to parse-then-extract from a shared
  tree, enabling the reliability check without changing their public signatures.

## [1.0.2] - 2026-06-11

Parser-accuracy release. Every change reduces false positives or raises the
resolution rate of the regex fallbacks (used when the optional `[tree-sitter]`
extra is not installed). Fully backward-compatible.

### Added
- **Comment-aware regex fallbacks** — a shared, string-aware `strip_comments`
  pass removes `//`, `/* */` (and `#` for PHP) comments before import matching,
  so import-like text inside comments no longer produces phantom dependencies.
  Applied to JavaScript/TypeScript, Java, C#, PHP and C/C++. String literals
  (e.g. `require("x")`, `#include "x"`) are preserved, and line structure is
  kept intact for `re.MULTILINE` matching.
- **Go `replace` directives** — local replacements in `go.mod`
  (`replace x => ./local`) now resolve imports to the replaced directory instead
  of reporting them as external packages.
- **PHP composer PSR-4 autoload** — `use` statements resolve through the
  `autoload`/`autoload-dev` `psr-4` map in `composer.json` (longest prefix wins),
  replacing the previous fragile suffix-matching heuristic for configured roots.
- **C# alias and `global using`** — `using Alias = Real.Namespace;` now extracts
  the right-hand namespace (previously captured the alias name), and
  `global using` directives are recognized.
- **Java inner-class resolution** — `import com.example.Outer.Inner;` resolves to
  `com/example/Outer.java` when no `Inner` compilation unit exists.
- **C/C++ include-dir resolution** — a header included as `"foo/bar.h"` resolves
  to a unique `include/foo/bar.h` or `src/foo/bar.h` via path-suffix matching,
  covering the common `-I` include-directory layout.

### Changed
- C# `using static System.Math;` now parses to the `System.Math` namespace
  (the `static` directive keyword is no longer kept in the parsed value).

## [1.0.1] - 2026-06-11

Hardening and correctness release. No public API breakage — every change is
backward-compatible with 1.0.0.

### Security
- **`serve` binds to `127.0.0.1` by default** (was `0.0.0.0`). Exposing the
  server on the network now requires an explicit `--host` and prints a warning.
- **All state-changing / local endpoints gated to loopback** — `/api/project`
  (switch analyzed directory), `/api/reanalyze`, and `/api/advise` now require a
  loopback client, matching `/api/open` and `/api/open-file`. Previously a host
  on the same network could repoint the analyzer at any directory and read its
  structure via `/api/graph`, or trigger outbound LLM requests (SSRF).
- **`/api/advise` validates `base_url`** — only well-formed `http`/`https` URLs
  are forwarded server-side; `file://` and other schemes are rejected.

### Fixed
- **Whole-graph impact analysis is now O(V+E)** instead of O(V·E). The backward
  adjacency map is built once and shared across nodes (`impact_analyzer.build_dependents_map`),
  and the BFS uses a `deque` instead of `list.pop(0)`. Large repositories no
  longer spend most of the analysis time in impact calculation.
- **LLM advisor layer-violation rendering** — the prompt read non-existent
  `fromLayer`/`toLayer` keys and emitted `None -> None`. It now reads the
  `sourceLayer`/`targetLayer`/`source` fields actually produced by the risk
  analyzer.
- **Mermaid label escaping** — labels containing `\n`, `[` `]`, `{` `}`, `<` `>`,
  `"` or `\` no longer break the generated diagram; labels are quoted and the
  breaking characters are escaped or substituted.

### Added
- **tsconfig / jsconfig path-alias resolution** — JS/TS imports that rely on
  `compilerOptions.baseUrl` and `compilerOptions.paths` (e.g. `@app/*` → `src/*`)
  now resolve to internal files instead of being reported as external packages,
  raising `resolutionRate` on real-world TypeScript projects. JSONC comments and
  trailing commas in the config are tolerated.

### Changed
- **Coverage gate enforced in CI** — `--cov-fail-under=85` added to the pytest
  configuration; the suite now fails if coverage regresses below 85%.
- **Dockerfile pinned to `python:3.13-slim`** (was the unreleased `3.14-slim`).

## [1.0.0] - 2026-05-25

### Added
- **`archmap temporal`** — temporal coupling analysis via `git log`. Detects files that frequently change together in commits — hidden coupling not visible in static imports. Outputs ranked pairs with co-change count and coupling strength (0–1). Flags: `--min-commits N`, `--top N`, `--json`. Zero new dependencies (stdlib `subprocess` only).
- **Web UI — SVG export** — "SVG" button in the canvas toolbar next to PNG. Uses Cytoscape.js native `cy.svg({ full: true })` API and downloads as `archmap-graph.svg`. Scalable vector output, zero new dependencies.
- **MCP server** (`archmap mcp`) — exposes the ArchMAP analysis engine as a JSON-RPC 2.0 server over stdio. Four tools: `get_architecture_summary`, `get_file_context`, `impact_analysis`, `run_checks`. Compatible with Claude Code, Cursor, Windsurf, and any MCP-capable AI assistant.

### Changed
- **Stable public Python API** — `from archmap import analyze_project, AnalysisResult` is now fully typed and considered stable. All types exported from `archmap.types`. Zero-breaking-change commitment for all 1.x releases.
- **mypy strict enforcement** — 0 type errors enforced as a blocking CI gate. All new code must pass mypy at the same strictness level.
- **Test coverage** — raised to 88% (from 85% in v0.9.0). New test files: `test_reachability_analyzer`, `test_generic_parser`, `test_rust_go_parsers`, `test_temporal_analyzer`.

### Migration from 0.x

No breaking changes. The `analyze_project()` function and all return types are backward-compatible with 0.9.0. The only additions are:
- New `archmap temporal` subcommand.
- New SVG export button in the Web UI.
- New `archmap mcp` subcommand (available since 0.9.x, now stable).
- `from archmap import AnalysisResult` and all sibling types are now part of the public API contract.

## [Unreleased]

### Added
- **Tree-sitter multi-language parser** — optional `[tree-sitter]` extra (`pip install archmap[tree-sitter]`) replaces every regex-based parser with a proper AST engine. When the extra is installed, all nine language parsers use tree-sitter grammars:
  - **JavaScript / TypeScript** — `tree-sitter-javascript` / `tree-sitter-typescript` (+ TSX variant). Multiline imports, `import type`, `export type` all handled correctly. Import-like text in string literals and comments no longer produces false positives.
  - **Java** — `tree-sitter-java`. Static imports, wildcard imports (`com.example.*`), and standard imports all resolved correctly.
  - **Go** — `tree-sitter-go`. Both single-import and block-import forms captured without regex edge cases.
  - **Rust** — `tree-sitter-rust`. `use`, `mod`, and `extern crate` declarations extracted and normalised using the existing `_normalize_rust_use` logic.
  - **PHP** — `tree-sitter-php`. Handles both single-quoted and double-quoted strings, and the parenthesized call form (`require('x')`).
  - **C#** — `tree-sitter-c-sharp`. `using`, `using static`, and alias directives.
  - **C / C++** — `tree-sitter-c` / `tree-sitter-cpp`. `#include <system>` and `#include "local"` correctly distinguished by node type.
  - The regex fallback is preserved in all parsers; no behaviour change when the extra is not installed.
- **Per-import unresolved tracking** — parser now resolves each import statement individually. `importsTotal`, `importsResolved`, and `unresolvedImports` fields on every `ParsedFile`. `metrics.unresolvedImports` and `metrics.unresolvedImportsTotal` in the graph report.
- **`--show-unresolved[=N]`** — prints a detailed list of import statements that could not be resolved (file + specifier). `N` controls how many are shown (default 20 when flag is present).
- **`--fail-on-budget-violations`** — CI gate that exits with code 2 when any file exceeds coupling budgets. Works with CLI overrides or `.archmap.toml`.
- **`--max-outgoing-per-file N`** — CLI override for maximum allowed outgoing dependencies per file.
- **`--max-incoming-per-file N`** — CLI override for maximum allowed incoming dependencies per file.
- **`[analysis.budgets]` in `.archmap.toml`** — `max_outgoing_per_file` and `max_incoming_per_file` config keys for project-wide coupling limits.
- **`--ignore-external`** — strips external package nodes (e.g. `pkg:requests`) and their edges from the output graph. Metrics are recomputed after filtering. Useful for focusing on internal structure only.
- **`--summary-format {text,table,markdown}`** — controls the terminal summary output style. `text` (default) is the existing `[ok]/[warn]` format; `table` renders an aligned ASCII table with separator lines; `markdown` renders a pipe-delimited markdown table for pasting into docs or PRs.

### Fixed
- **SVG injection in `/api/badge`** — health grade string is now XML-escaped via `xml.sax.saxutils.escape` before being embedded in the SVG response. Prevents XSS if a grade value ever contained `<`, `>`, or `&`.
- **Web UI Config navigation** — Config panel is now accessible via a dedicated gear-icon button in the nav rail (`navBtnConfig`). The ArchMAP logo click is restored to its original behavior: navigating to the Graph view. Previously the logo opened Config, leaving no dedicated button and no way to return to the graph.
- **`_VALID_LLM_PROVIDERS` scoping in `server.py`** — moved to module-level `frozenset` constant; previously re-declared as a local variable inside `_handle_advise` on every request.

## [0.9.0] - 2026-05-08

### Added
- **Parser resolution rate** — `resolutionRate` metric (0.0–1.0) now included in every analysis report. Tracks what fraction of import statements were successfully resolved to a file or package. Visible in the CLI summary (warns when below 70%), in the Web UI Insights panel, and in JSON output (`metrics.resolutionRate`). New `--min-resolution-rate PCT` flag gates CI on this metric (e.g. `--min-resolution-rate 70`).
- **Shell completion** — `archmap --print-completion bash|zsh|fish` prints the shell-specific setup command. Install the `argcomplete` optional dep (`pip install archmap[completion]`) and add the printed line to your shell profile for full tab-completion of all subcommands and flags.
- **Web UI — PNG export** — "PNG" download button in the canvas toolbar. Exports the current dependency graph as a 2× scale PNG using Cytoscape.js's native `cy.png()` API. Zero new dependencies.
- **Docker image** — `ghcr.io/kaua-kgzin/archmap:latest` published automatically on each GitHub release. Includes `:X.Y.Z` and `:X.Y` version tags. Use `docker run -p 3000:3000 -v $(pwd):/project ghcr.io/kaua-kgzin/archmap` to start the Web UI.
- **Web UI — i18n** — Full interface internationalization: English, Português (Brasil), Español, Français, Deutsch, 中文 (简体). Language selector in the Config panel; setting persists across sessions and applies instantly without reload.
- **Web UI — Config panel** — Clicking the ArchMAP logo opens a persistent settings panel: Interface (language), General (auto-save config, animations toggle), Graph (default layout: cose/breadthfirst/concentric/circle/grid), LLM Advisor, Scan Languages. All settings saved to localStorage.
- **Web UI — Advisor persistence** — LLM provider, model, base URL, and API key are saved to localStorage and restored on every session. Auto-save mode writes on every keystroke.

### Changed
- `metrics.resolutionRate` field added to the JSON report schema (always present, defaults to `1.0` when no imports are found).

## [0.8.0] - 2026-05-07

### Added
- **`archmap trace <entrypoint>`** — BFS reachability analysis from any source file: shows the full dependency tree by depth level, coverage percentage, and optionally lists unreachable files (`--unreachable`). Supports `--max-depth`, `--json`, and `--out`.
- **`archmap advise`** — LLM-powered architectural advisor. Sends a compact report summary to an LLM and returns concrete refactoring advice. Supports multiple providers with zero new runtime dependencies (pure `urllib`):
  - `--provider claude` — Anthropic API (reads `ANTHROPIC_API_KEY`)
  - `--provider openai` — OpenAI API (reads `OPENAI_API_KEY`)
  - `--provider ollama` — local Ollama instance (default `http://localhost:11434`)
  - `--provider custom --base-url <url>` — any OpenAI-compatible endpoint (LM Studio, etc.)
  - `--model`, `--api-key`, `--timeout` flags for full control.
- **`archmap init --from-analysis`** — analyzes the project first and derives `.archmap.toml` layer rules from actual dependency direction (files with higher fan-in rank as more foundational), including detected `forbid` rules from live violations.
- **`archmap diff --snapshot-a <file> --snapshot-b <file>`** — compare two exported JSON snapshots directly, without requiring git refs. Useful for cross-machine or cross-deploy comparisons.
- **VS Code extension** (`vscode-extension/`) — zero-config IDE integration:
  - Inline diagnostics in the Problems panel for cycles, layer violations, god modules, and custom rule violations.
  - Status bar item with live health score and grade.
  - `ArchMAP: Analyze Project` command.
  - `ArchMAP: Open Web UI` command (launches `archmap serve` and opens browser).
  - `ArchMAP: Trace File Reachability` command — opens a webview with the BFS depth tree.
  - `archmap.analyzeOnSave` setting for CI-style continuous feedback.

## [0.7.2] - 2026-04-27

### Added
- **Web UI — multi-view navigation**: nav rail now switches between three independent left-panel views (Graph, Insights, Rules & Layers).
- **Web UI — Layer Diagram tab**: new canvas tab renders the dependency graph with a hierarchical breadth-first layout and a floating legend.
- **Web UI — Dependency Matrix tab**: new canvas tab renders the top-25 most-connected files as a colour-coded dependency matrix (dependency, circular, self-reference).
- **Web UI — Insights panel**: architecture metrics summary cards populated live from report data (health score, files, cycles, complexity, etc.).
- **Web UI — Rules & Layers panel**: displays layer rule cards from `.archmap.toml`; shows a "no rules configured" placeholder when absent.
- Breadcrumb and canvas title update dynamically when switching canvas tabs.

## [0.7.1] - 2026-04-27

### Fixed
- **Web UI**: bundle Cytoscape 3.30.2 locally — eliminates CDN dependency and fixes broken graph (CSP was blocking `unpkg.com`).
- **Web UI**: correct Content-Security-Policy to allow Google Fonts while keeping scripts same-origin.
- **CI (windows-exe)**: add `pillow` to PyInstaller deps so `icon.png` → `.ico` conversion works on the runner.
- **PyPI publish**: align package name with PyPI project (`KG-ARCHMAP`) so OIDC trusted publisher accepts uploads.
- **PyPI publish**: add `skip-existing: true` to avoid 400 errors on re-runs of the same tag.

### Changed
- **Web UI**: complete visual refresh — Inter + JetBrains Mono fonts, indigo design system, architecture health gauge, KPI tiles, ranked critical files list, selection grid, status bar, mini-map overlay.

## [0.7.0] - 2026-04-24

### Added
- **TypeScript parser** with triple-slash reference support (`/// <reference path="..." />`).
- **Reusable GitHub Action** (`action.yml`) — run ArchMAP analysis directly in any workflow with SARIF upload to GitHub Code Scanning.
- **Pre-commit hook** via the `archmap-check` entrypoint — integrates with `.pre-commit-hooks.yaml` for zero-config quality gates.
- **Incremental parse cache** — unchanged files are skipped on re-analysis, reducing runtime on large repos.
- **`--sarif` flag** on `archmap analyze` — exports findings as SARIF 2.1.0 for upload to Code Scanning or SAST tools.

### Changed
- Parser registry now self-registers at import time; `bootstrap.py` is a no-op retained for backwards compatibility.
- Web UI simplified: removed i18n layer, reduced bundle size.
- `archmap-check` pre-commit entrypoint defaults: `--quiet --fail-on-cycles --fail-on-custom-rules`.

### Removed
- `architecture_analyzer`, `architecture_suggester`, `history_analyzer`, `human_analyzer`, `impact_analyzer` — these experimental analyzers were removed to reduce scope and maintenance burden.
- `explain`, `risk`, `improve`, `history` CLI commands — backends removed; commands raise `NotImplementedError` and will be fully cleaned from the CLI in v0.8.0.
- i18n layer from the web UI (`i18n.js`).

## [0.4.0-beta.0] - 2026-03-09

### Added
- **Multi-Language Registry:** Overhauled the parser architecture to support plugin-based language detection. Added support for **Go, PHP, Java, C#, C, and C++**.
- **"UI of Respect" (Web UI v2):**
  - **Dark Mode Support:** Full dark theme with session persistence.
  - **Architectural Risks Panel:** Live detection of circular dependencies and "Hub modules".
  - **Dynamic Project Import:** New folder icon in the UI allows switching the analysis target on the fly via a native directory picker (no restart required).
  - **Real-time Refresh:** Manual data re-polling for instant graph updates.
- **Respectful Executable (EXE):**
  - **Standalone Launcher:** Double-clicking the EXE now automatically launches the interactive Service Map.
  - **Persistent Error Log:** Added a "Press Enter to exit" pause on errors in the frozen executable for easier troubleshooting.
  - **Premium Branding:** Embedded high-resolution project icon and professional CLI banner.

### Fixed
- **CI Stabilization:** Resolved 22 linting regressions and updated the test suite to ensure 100% compatibility with the new parser architecture.
- **Repository Cleanup:** Removed redundant legacy JavaScript files from the root to ensure a clean Python-centric distribution.

## [0.2.1] - 2026-03-07

### Added
- **OSS Professionalization:** Added Issue Templates (Bug/Feature), Code of Conduct, and detailed architecture & API documentation.
- **Documentation Site:** Implemented MkDocs Material site with automated GitHub Pages deployment.
- **Professional CI:** Expanded CI to test against Python 3.11, 3.12, and 3.13.
- **Automated Releases:** Added GitHub Actions workflow to automate package building and releases on version tags.
- **Rich Examples:** Enriched `examples/sample-project` with intentional cycles and layer violations for demonstration.
- **Benchmark Tool:** Added `scripts/benchmark.py` for performance testing.

### Fixed
- **Static Assets:** Fixed "Web UI static directory not found" error in packaged (wheel) installations by using `importlib.resources`.
- **Parser Precision:** Fixed dependency resolution for absolute `from ... import ...` submodules that were previously misidentified as package-level dependencies.

## [0.1.3] - 2026-03-05

### Added
- **Single File Analysis:** Added support to natively read and resolve dependencies starting from a single file instead of a full directory scan, reducing overhead and providing concise maps for entry files.
- **Standalone Windows Executable (`.exe`):** Bundled the CLI and the Web UI into a completely portable, zero-dependency Windows executable via PyInstaller. The interactive graph server (`archmap.exe serve .`) operates directly without a Python runtime requirement.

### Changed
- Rebuilt architecture file crawler (`file_utils.discover_source_files`) to intercept root files before deep recursive searches.

## [0.2.0-beta.0] - 2026-03-04

### Added
- Full Python implementation under `src/archmap`.
- New Python CLI with commands:
  - `analyze`
  - `serve`
  - `diff`
- Architecture risk engine with:
  - god module detection
  - layer violation detection
  - dependency explosion detection
- Cytoscape exporter (`cytoscape_exporter.py`).
- `pyproject.toml` with package metadata and scripts.
- Pytest suite for parser, analyzer, exporters, CLI, and diff.
- CI pipeline with Ruff lint + pytest coverage + smoke analysis.

### Changed
- Canonical runtime migrated from Node.js to Python.
- Repository structure aligned to `src/archmap` layout.
- Branch strategy documented as:
  - `feature/* -> dev -> release/* -> main`

### Notes
- JavaScript implementation is no longer the primary runtime.
- Next target: `v0.3.0` architecture policy and trend analysis.
