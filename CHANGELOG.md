# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

No entries yet.

## [0.6.0] - 2026-04-15

### Added
- `SECURITY.md` with vulnerability reporting policy and supported versions.
- `.github/CODEOWNERS` for automatic review assignment.
- PEP 561 `py.typed` marker for typed package compliance.
- Content-Security-Policy meta tag on the web UI for defense-in-depth.
- `crossorigin="anonymous"` on all external CDN resources.

### Changed
- CLI banner now only prints on interactive terminals, preventing corruption
  of piped JSON output.
- Bare `except Exception` handlers replaced with specific exception types
  (`OSError`, `RuntimeError`, `ValueError`) across `server.py` and `main.py`.
- Portuguese log messages in `project_parser.py` translated to English for
  international consistency.
- `.gitignore` expanded with environment/secret patterns (`.env`, `*.pem`,
  `*.key`), egg artifacts, IDE folders, and OS files.
- `max_file_size_bytes` configuration now enforces a 100 MB hard ceiling to
  prevent resource exhaustion from misconfigured values.

### Fixed
- All `subprocess` calls in `diff_analyzer.py` now include a 120-second
  timeout, preventing indefinite hangs on slow or corrupted Git operations.
- HTTP request body reader validates `Content-Length` with a 1 MB cap and
  guards against malformed header values.
- `tkinter` root window is now destroyed in a `finally` block, preventing
  orphaned windows when the directory picker raises.
- SSE listener list is now protected by a `threading.Lock` for safe
  concurrent access across handler threads.
- Path traversal protection strengthened: both candidate and project root are
  fully resolved before the containment check.
- Node.js `runProcess` uses `Buffer.concat` instead of string concatenation
  for stderr collection.

### Security
- Added `Content-Length` limit (1 MB) to prevent memory exhaustion via
  oversized request bodies.
- Subprocess timeout (120s) prevents denial-of-service through stalled Git
  processes.
- Strengthened path resolution guards against symlink-based traversal.
- Added Content-Security-Policy header to the web UI.

## [0.6.0b0] - 2026-03-30

### Added
- Automatic architecture suggestion engine via `ArchitectureSuggester`.
- New CLI commands:
  - `archmap explain`
  - `archmap risk`
  - `archmap improve`
- `archmap improve --out-script` to generate a helper refactor script.
- Human-readable architecture insights and automatic project explanation in CLI output.
- Optional impact analysis during `archmap analyze` through `--impact`.
- Documentation pages for `init`, `watch`, `explain`, `risk`, and `improve`.

### Changed
- `archmap analyze` now behaves better as a zero-config entry point for day-to-day use.
- `archmap improve` now prefers stable folder suggestions such as `shared`, `app`,
  `core`, `cli`, and domain folders instead of generating paths from raw file names.
- CLI terminal output is now ASCII-safe, which improves Windows compatibility.
- Repository metadata, package versions, README, MkDocs navigation, and repo links
  were synchronized to the `ArchMAP` repository and the `0.6.0b0` release line.

### Fixed
- Fixed Windows `charmap` crashes caused by Unicode-heavy terminal output.
- Restored backward-compatible handling for CLI args such as `no_subgraphs`.
- Prevented duplicate target-path collisions in automatic refactor suggestions when
  multiple files share the same basename.
- Closed the remaining Ruff regressions and kept the full pytest suite green.

## [0.5.0-beta.0] - 2026-03-25

### Added
- Project configuration via `.archmap.toml` / `archmap.toml`, including `analysis.ignore_dirs`, `analysis.max_file_size_bytes`, `architecture.rules`, and customizable `risks.layer_order`.
- Architecture intelligence:
  - automatic style inference (`monolith`, `modular_monolith`, `microservice_like`)
  - architecture health score and grade
  - custom `forbid` / `allow` rule validation
  - diff output with architecture-health deltas
- Historical architecture analysis from Git:
  - graph evolution timeline
  - cycle origin tracking
  - hotspot ownership / blame hints
  - CLI `history` command and `/api/history` endpoint
- UI workflow improvements:
  - project pinning for quick reopening
  - language switching (`pt-BR`, `en`, `ru`, `zh-CN`)
  - explicit theme selection (`dark`, `light`, `ocean`)
  - clearer selection actions for opening files, focusing modules, and returning to project view
- File-level diff summaries (`added`, `removed`, `changed`) and Git content loading through `git cat-file --batch`.
- Shared pytest fixtures for graph nodes, edges, parsed files, and temporary project layouts.
- Release artifacts for this version:
  - `dist/archmap.exe`
  - `dist/archmap-0.5.0-beta.0.exe`
  - `dist/archmap-build-info.json` (SHA256: `2AFC6941309AE3CBD87508FDDC2A8D20393D0DF4E40A774B7F0B38E7227D814B`)

### Changed
- CLI architecture split from a single large `main.py` into focused modules for arguments, commands, defaults, reporting, and server behavior.
- Parser package reorganized into dedicated bootstrap, resolver, project parsing, and TypeScript modules.
- Python dependency parsing now uses `ast` first, with a tolerant fallback for incomplete files.
- JavaScript/TypeScript scanning now ignores comments, strings, and more dynamic-import edge cases more reliably.
- Complexity scoring now considers outgoing imports, incoming dependents, total connections, and instability-oriented coupling metrics.
- Default analysis scope now excludes common generated and non-production folders such as `site/`, `tests/`, `examples/`, and `.codeatlas/`.
- Web UI layout refreshed with stronger visual hierarchy, richer project controls, and clearer action affordances.

### Fixed
- Python `src/` layout imports now resolve as internal files instead of external packages.
- Cycle detection now uses an iterative SCC walk instead of recursive traversal, preventing recursion depth failures on large graphs.
- Project switching in the UI now falls back cleanly when the native directory picker is unavailable.
- `localStorage` access in the web UI is guarded to avoid runtime errors in restricted environments.
- Mermaid node identifiers are sanitized consistently for generated diagrams.
- Tracked text files were normalized to LF to avoid mixed line-ending drift across environments.
- Release metadata now aligns across Python package version, Node package version, README badges, and documentation links.

### Testing
- Coverage increased to 89-90% across the expanded suite.
- Added direct regression coverage for CLI internals, server endpoints, parser registry/bootstrap internals, file discovery rules, risk scoring, max-file-size behavior, architecture analysis, history analysis, and web UI asset parity.

## [0.4.0-beta.1] - 2026-03-11

### Added
- Governance and release assets:
  - `NOTICE.md` with original distribution attribution for Kauã Gabriel.
  - PR template with mandatory quality checklist.
  - Demo script: `scripts/demo.ps1`.
  - EXE build automation: `scripts/build-exe.ps1` with hash manifest and smoke test.
- Documentation pages for:
  - live demo
  - logging/artifact policy
  - MkDocs governance/project wrapper pages
- Architecture release assets:
  - `dist/archmap.exe`
  - `dist/archmap-0.4.0-beta.1.exe`
  - `dist/archmap-build-info.json` (SHA256: `A20BA6CE1FAEADE8948F0628A1C79A5DBB4CBFC4E0A09B954FA3E386650BF67E`)
- Graph UX improvements:
  - semantic node coloring by role (controller/model/service/request/database/external/other)
  - node sizing by dependency importance
  - weighted edges and explicit circular edge highlighting
  - mini-map navigation with viewport indicator
  - dependency focus depth and expand/collapse controls
  - cluster by folder mode
  - architecture health score and hotspot panel
  - PNG graph export

### Changed
- Branch flow documentation standardized to `feat/* -> dev -> release/* -> main` (with legacy `feature/*` support).
- Repository hygiene:
  - root loose logs moved to `logs/archive/`
  - runtime logs standardized in `logs/runtime/`
  - generated build artifacts removed from source tracking policy
- README rewritten with:
  - professional Git workflow
  - demo commands
  - folder governance
  - attribution section
- CLI startup banner now shows copyright line for `Kaua-KGzin`.

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
