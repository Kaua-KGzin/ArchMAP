# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

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
