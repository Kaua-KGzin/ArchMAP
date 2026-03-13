# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- No entries yet.

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
