# ArchMAP Roadmap

## Released

### v0.8.0 (current)
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

## Next up (v0.8.x / v0.9.0)

- **CLI coverage** — `tests/test_args.py`, `tests/test_commands.py`, `tests/test_reporting.py` to bring coverage ≥ 85%.
- **Server security** — `/api/project` path validation (`allowed_roots`), rate limit on `/api/reanalyze`.
- **`--quiet` flag** — fully silent mode for CI pipelines.
- **Dead-code detector** — surface unreferenced files and exports.
- **Architectural Blueprint** — target-state enforcement from `.archmap.toml` layer rules.
- **Dynamic health badge** — `/api/badge` endpoint for README embedding.

---

## Medium-term (v0.9.x)

- **Shell completion** — bash, zsh, and fish autocompletion via `argcomplete` or `shtab`; `archmap --print-completion bash` convenience flag. Critical DX gap for power users and CI environments.
- **Docker image** — Official `ghcr.io/kaua-kgzin/archmap:latest` image, published automatically on each release via GitHub Actions. Enables CI use without requiring Python installed in the runner.
- **Parser resolution rate** — Expose `resolution_rate` (resolved imports ÷ total imports) in JSON output, Web UI, and CLI summary. Warn when below 70%. Add `--min-resolution-rate` gate for CI. Makes parser confidence visible and prevents silently misleading graphs.
- **Public Python API** — Define and document a stable programmatic surface (`from archmap import analyze_project, ArchMapConfig, AnalysisResult`). Add `__all__` to public modules, document with MkDocs examples, establish a deprecation policy (`DeprecationWarning` + semver). Unlocks IDE plugins, pytest integrations, and custom CI tooling beyond the CLI.
- **mypy enforcement (blocking)** — Graduate mypy from non-blocking (infrastructure only, v0.8.x) to a hard CI gate. Expand typed coverage module by module until `--strict` is feasible on the full `src/archmap/` tree.

---

## Longer-term (v0.9.0+)

- Plugin SDK for custom parsers and analyzers via entry points.
- Change coupling detector via `git log` analysis.
- Complexity budget enforcement per module.
- Multi-repo topology support.
- WebSocket-based live UI refresh.
- GraphML and Graphviz DOT export formats.
- **Tree-sitter based parsers** — Replace regex-based parsers for JS, TS, Java, PHP, C#, and C++ with `tree-sitter` bindings (Python: `tree-sitter`, `tree-sitter-javascript`, etc.). The Python parser already uses the native AST; applying the same rigor to all languages is the most impactful quality improvement possible. Regex parsers silently misclassify multiline imports, template literals, decorators, and comment-embedded patterns — contaminating every downstream analysis (cycles, risk, trace, LLM advisor).
- **Property-based testing (Hypothesis)** — Add `hypothesis` to dev deps and use it on all language parsers. Principle: the parser must never crash on any valid unicode input. Finds edge cases that fixed-example tests miss, particularly important for parsers processing untrusted user code.
- **Mutation testing (mutmut)** — Apply mutation testing to the core analysis modules (`cycle_detector.py`, `risk_analyzer.py`, `complexity_analyzer.py`). Exposes tests that pass accidentally and enforces that the test suite would actually detect bugs in the logic it covers.
- **Homebrew formula** — Distribute ArchMAP as a Homebrew tap for macOS users (`brew install kaua-kgzin/tap/archmap`). Complements the existing PyPI + Windows EXE distribution and removes the Python-install barrier for macOS developers.
- **Web UI accessibility (a11y)** — Audit and fix WCAG 2.1 AA compliance in the Web UI: color contrast, keyboard navigation, focus management, ARIA labels for the Cytoscape.js graph. Add `axe-core` to the CI test suite for regression detection.
- **Web UI graph export** — Add a "Download PNG" and "Download SVG" button to the Web UI using Cytoscape.js's native `cy.png()` and `cy.svg()` APIs. Zero new dependencies; high user value for documentation and presentations.
- **API stability policy** — Publish a formal versioning contract: which modules are public API (stable across minor versions), which are internal (may break), and what the deprecation timeline is. Correlate with the `__all__` work from the medium-term public API item.

---

## Continuous

These are ongoing commitments rather than versioned deliverables. They run in parallel with every release cycle.

- **Supply chain audit** — `pip-audit` runs in CI on every push (implemented in v0.8.x). Dependabot watches Python deps, npm deps, and GitHub Actions pins on a weekly schedule. No manual audit cadence required.
- **Architectural self-check (dogfooding)** — CI runs `archmap analyze src/archmap/ --fail-on-cycles` on every push. ArchMAP must pass its own analysis. The health score threshold (`--min-health`) is raised incrementally as the codebase improves, making the gate self-tightening.
- **mypy coverage expansion** — Type annotations are added incrementally to every new or modified file. The mypy CI step starts non-blocking (infrastructure, v0.8.x) and transitions to a hard gate (v0.9.x) once baseline coverage is established. No new untyped functions merged after v0.9.0.
- **Documentation freshness** — Every CLI flag, JSON output field, and `.archmap.toml` key introduced in a PR must be documented in the same PR. The MkDocs build runs with `--strict` in CI; broken references fail the docs workflow.
- **Parser parity** — As new language features are introduced (e.g., Python 3.12+ type parameter syntax, TypeScript 5.x satisfies operator), parser regression tests are added before the parser update is merged. No silent parser regressions.
