# Predictable Cost at Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ArchMAP's analysis grows close to linearly, users can see expected time and memory before running (`--estimate`), and a soft time budget (on by default in MCP) degrades visibly instead of hanging.

**Architecture:** A new `archmap.core.perf` package holds the synthetic project generators, the stage timer, the estimate model and the budget. `analyze_graph` takes a `Budget` and records per-stage timings and reductions. Impact moves to an SCC-condensation algorithm with a capped list; consumers that need the full list call one single-node BFS helper.

**Tech Stack:** Python 3.10+ stdlib only (`tracemalloc`, `time`, `concurrent.futures`), pytest, argparse, MkDocs.

**Spec:** `docs/superpowers/specs/2026-11-26-predictable-scale-design.md`

## Global Constraints

- Python stdlib only for new runtime code; no new dependency in `pyproject.toml`.
- JSON report fields keep their names; new fields are additive (`impactedFilesTruncated`, `metrics.analysisQuality.timingsMs` stage keys, `metrics.analysisQuality.reductions`).
- `IMPACT_LIST_CAP = 200`, always on. Nodes impacting ≤ 200 files are byte-identical to today.
- `impactCount` and `risk` stay exact for every node.
- MCP default budget: 120 s. CLI and GitHub Action: no budget by default. `0` means no limit everywhere.
- Every active default budget or reduction is announced, with how to change it (CLI line, MCP `notice`, `QUAL-*` finding, docs).
- Reduced runs are never cached; the cache fingerprint includes the budget and a report schema version.
- Progress goes to stderr only, only when stderr is a TTY, never with `--quiet`.
- Termux numbers are out of scope (v1.8.0); `docs/performance.md` says so.
- Project rules: work on `feat/predictable-scale`, PR with the AI-assistance section, docs in the same PR, `mkdocs build --strict`, ruff, mypy, `archmap analyze src/archmap/ --fail-on-cycles`.

Test command used throughout: `.venv/Scripts/python.exe -m pytest` (Windows) / `python -m pytest`.

## Review Focus

- Empty or source-less directory with `--estimate`: prints 0 files and a 0 s estimate, exit 0 (test in Task 6).
- `--estimate --format json` and any `--format json` run: stdout is valid JSON only; no progress or notice text on stdout (tests in Tasks 6 and 9).
- Negative `--time-budget` / `time_budget_seconds`: rejected with a clear error, not treated as "no limit" (test in Task 7).
- Node impacting exactly 200 files is not truncated; 201 is (test in Task 2).
- Package nodes (`pkg:redis`): capped like files, and the MCP `impact_analysis` / `expose` full list still works for them (test in Task 3).

---

### Task 1: Stage timings and the synthetic benchmark suite

**Files:**
- Create: `src/archmap/core/perf/__init__.py`, `src/archmap/core/perf/synthetic.py`, `src/archmap/core/perf/timing.py`
- Modify: `src/archmap/core/analyzer/dependency_graph.py` (`analyze_graph`), `scripts/benchmark.py`
- Test: `tests/test_perf_synthetic.py`, `tests/test_stage_timings.py`

**Interfaces:**
- Produces:
  - `generate_project(root: Path, n_files: int, *, language: Literal["python", "typescript"] = "python", shape: Literal["layered", "hub", "cycle"] = "layered", seed: int = 0) -> None` in `synthetic.py`. Deterministic for a given seed. `cycle` reproduces today's benchmark (each file imports its 5 wrap-around neighbours). `layered`: 10 layers, each file imports 3–5 files from lower layers only. `hub`: 20 hub files, every other file imports 3 hubs plus 1 neighbour.
  - `class StageTimer` in `timing.py`: `with timer.stage("impact"): ...`; `timer.as_dict() -> dict[str, float]` (ms, rounded to 0.1).
  - `analyze_graph(..., timer: StageTimer | None = None)`. Stage names: `"cycles"`, `"impact"`, `"risk"`, `"testMapping"`, `"centrality"`, `"findings"`. They are merged into `metrics.analysisQuality.timingsMs` next to the existing `discover` / `parse`.
  - `scripts/benchmark.py`: `--sizes 1000,5000`, `--language`, `--shape`, `--json OUT`, `--repeat N`. Always calls `analyze_project(..., use_cache=False)`. Measures peak memory with `tracemalloc`. JSON rows: `{"files", "language", "shape", "seconds", "peakMb", "edges", "stagesMs"}`, plus `{"machine": {"python", "platform", "cpuCount"}}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_generate_project_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate_project(a, 50, shape="layered", seed=1)
    generate_project(b, 50, shape="layered", seed=1)
    assert sorted(p.read_text() for p in a.rglob("*.py")) == sorted(p.read_text() for p in b.rglob("*.py"))

def test_layered_shape_has_no_cycles(tmp_path):
    generate_project(tmp_path, 200, shape="layered")
    assert analyze_project(tmp_path, use_cache=False)["cycles"] == []

def test_typescript_generator_resolves_imports(tmp_path):
    generate_project(tmp_path, 100, language="typescript", shape="hub")
    report = analyze_project(tmp_path, use_cache=False)
    assert report["metrics"]["analysisQuality"]["resolutionRate"] >= 0.99   # use the real key name in quality.py

def test_stage_timings_present(tmp_path):
    generate_project(tmp_path, 30)
    t = analyze_project(tmp_path, use_cache=False)["metrics"]["analysisQuality"]["timingsMs"]
    assert {"discover", "parse", "cycles", "impact", "centrality"} <= t.keys()
```

- [ ] **Step 2: Run them, expect FAIL** (`ModuleNotFoundError: archmap.core.perf`). Run: `python -m pytest tests/test_perf_synthetic.py tests/test_stage_timings.py -v`
- [ ] **Step 3: Implement `synthetic.py`, `timing.py`, thread `timer` through `analyze_graph` and `analyze_project`, rewrite `scripts/benchmark.py` on top of `generate_project`.**
- [ ] **Step 4: Run the tests, expect PASS.** Then run `python scripts/benchmark.py --sizes 1000,2000 --shape cycle` and confirm it reproduces roughly today's numbers (≈0.3 s / ≈4.6 s on the dev machine) with `impact` dominating `stagesMs`.
- [ ] **Step 5: Commit** — `git commit -m "perf: stage timings and synthetic benchmark suite"`

### Task 2: Impact on the SCC condensation, capped list

**Files:**
- Modify: `src/archmap/core/analyzer/impact_analyzer.py`, `src/archmap/core/analyzer/dependency_graph.py:50-52`, `src/archmap/types.py` (`ImpactResult`)
- Test: `tests/test_impact_scale.py`

**Interfaces:**
- Consumes: `StageTimer` (Task 1).
- Produces:
  - `IMPACT_LIST_CAP: int = 200` in `impact_analyzer.py`.
  - `calculate_all_impacts(node_ids: list[str], edges: list[dict], *, list_cap: int = IMPACT_LIST_CAP, should_stop: Callable[[], bool] | None = None) -> dict[str, ImpactResult]`. Covers every node passed in (file **and** package nodes, as today).
  - `ImpactResult` gains `impactedFilesTruncated: NotRequired[bool]` (present and `True` only when truncated).
  - `calculate_impact(...)` stays (single node, full list, unchanged signature) for callers and tests.

Algorithm (the signature doesn't determine it): build the reverse graph (target → dependents), find SCCs on it (iterative Tarjan; no recursion), process components in reverse topological order so each component's reach set = union of its members' successors' reach sets plus the component itself. Represent reach sets as Python `int` bitsets over component indices; `impactCount` = number of nodes in the reached components (own component included) excluding the node itself, which is exactly what today's BFS returns, since it never lists the start node. Materialise `impactedFiles` only up to `list_cap` sorted entries (sort the reached node ids, take the first `list_cap`). `should_stop` is checked once per component; if it returns `True`, the remaining nodes get the list cap reduced to 0 but `impactCount` still exact (bitset work continues; only list materialisation is skipped).

- [ ] **Step 1: Write the failing tests**

```python
def test_matches_bfs_on_random_graphs():          # 30 random graphs, 1-60 nodes, with cycles and packages
    for seed in range(30):
        ids, edges = random_graph(seed)
        fast = calculate_all_impacts(ids, edges, list_cap=10_000)
        for n in ids:
            assert fast[n] == calculate_impact(n, edges)

def test_cap_boundary():                          # star(n): "hub" plus n files that each import it
    assert "impactedFilesTruncated" not in calculate_all_impacts(*star(200))["hub"]
    r = calculate_all_impacts(*star(201))["hub"]
    assert r["impactCount"] == 201 and len(r["impactedFiles"]) == 200 and r["impactedFilesTruncated"] is True

def test_package_node_capped(): ...               # 'pkg:redis' with 250 importing files → truncated, count 250

def test_worst_case_cycle_is_fast(tmp_path):
    generate_project(tmp_path, 5000, shape="cycle")
    t = analyze_project(tmp_path, use_cache=False)["metrics"]["analysisQuality"]["timingsMs"]["impact"]
    assert t < 3000                                 # today ≈ 20 000 ms on the dev machine
```

- [ ] **Step 2: Run, expect FAIL** (`ImportError: calculate_all_impacts`).
- [ ] **Step 3: Implement `calculate_all_impacts`; replace the per-node loop in `analyze_graph` with one call.**
- [ ] **Step 4: Run `tests/test_impact_scale.py` and the full suite, expect PASS.** Golden check: `python -m archmap.cli.main analyze . --no-cache --format json --out <tmp>` before and after this task gives identical JSON (ArchMAP's own nodes are under the cap).
- [ ] **Step 5: Commit** — `perf(impact): SCC condensation and capped impactedFiles`

### Task 3: Full impact list on demand for MCP, CLI report and expose

**Files:**
- Modify: `src/archmap/core/analyzer/impact_analyzer.py`, `src/archmap/cli/mcp_server.py:117-140`, `src/archmap/cli/reporting.py:95-135`, `src/archmap/core/exposure/correlate.py:35-50`
- Test: `tests/test_impact_on_demand.py`

**Interfaces:**
- Consumes: `calculate_impact`, `impactedFilesTruncated` (Task 2).
- Produces: `full_impacted_files(report: dict, node_id: str) -> list[str]` in `impact_analyzer.py`: returns the stored list when not truncated, else `calculate_impact(node_id, report["edges"])["impactedFiles"]`.

- [ ] **Step 1: Failing tests:** for a report with a 250-dependent package node, `_tool_impact_analysis(...)["impactedFiles"]` has 250 entries; `correlate` match for that package has 250; `print_impact_analysis` output still ends with `... and N more files` using the count. For an untruncated node, outputs are identical to before (snapshot of the existing tests passes unchanged).
- [ ] **Step 2: Run, expect FAIL** (MCP returns 200).
- [ ] **Step 3: Implement `full_impacted_files` and use it in the three call sites.**
- [ ] **Step 4: Run, expect PASS** (new tests + `tests/test_mcp_server.py`, `tests/test_exposure_correlate.py`, `tests/test_cli_reporting.py`).
- [ ] **Step 5: Commit** — `fix(impact): full list on demand where consumers need it`

### Task 4: Parsing hot spots

**Files:**
- Modify: `src/archmap/utils/file_utils.py:72` (`normalize_file_id`), `src/archmap/core/parser/__init__.py:107-165`
- Test: `tests/test_parse_perf.py`

**Interfaces:** none new; `parse_project` signature unchanged.

- [ ] **Step 1: Failing tests:** after parsing a 200-file `layered` project, `normalize_file_id.cache_info().hits > 0`; and a spy on the Python parser's `resolve` shows it is called once per import entry (today: once for the whole list plus once per entry). The speed check is a measurement in Step 4, not a test.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Memoise `normalize_file_id` with `functools.lru_cache(maxsize=65536)`; in `_parse_one`, resolve each entry once and build `dependencies` from those per-entry results (deduplicated in the order the whole-list call produces today), instead of resolving the whole list and then every entry again.** Dependencies must stay identical (order included); the full suite proves it.
- [ ] **Step 4: Run the full suite, PASS; benchmark `--sizes 2000 --shape layered` shows parse ≥ 30 % faster.** Then try a `ProcessPoolExecutor` path behind file count ≥ 2,000 (worker gets the file id list chunk + project root and re-creates the resolver context). Keep it only if the 20k `layered` run is ≥ 25 % faster end to end on the dev machine and the suite passes; otherwise drop it and note the measurement in the PR. Either outcome is fine.
- [ ] **Step 5: Commit** — `perf(parse): memoise ids, resolve each import once`

### Task 5: Baseline numbers and the coefficient table

**Files:**
- Create: `benchmarks/baseline.json`, `src/archmap/core/perf/coefficients.json`, `scripts/fit_estimate.py`
- Test: `tests/test_coefficients.py`

**Interfaces:**
- Produces: `coefficients.json` = `{"schema": 1, "reference": {"calibrationSeconds": float}, "languages": {"<lang>": {"secondsPerFile": float, "secondsPerKb": float}}, "default": {...}, "memory": {"baseMb": float, "mbPerFile": float}, "range": {"low": 0.5, "high": 2.0}}`. Loaded with `importlib.resources`; included in the wheel (check `pyproject.toml` package-data).

- [ ] **Step 1: Failing test:** `load_coefficients()` (in `perf/estimate.py` stub) returns the schema above, every language in `SUPPORTED_EXTENSIONS` resolves to a row (or `default`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Run the benchmark (1k/5k/20k/50k × python/typescript × layered/hub/cycle, `--json benchmarks/baseline.json`), fit with `scripts/fit_estimate.py` (least squares on the layered + hub rows; cycle rows are checked, not fitted), write `coefficients.json`. Languages without a generator use `default` = the python row.**
- [ ] **Step 4: Test passes; the 50k layered run finishes and its peak memory is recorded.**
- [ ] **Step 5: Commit** — `perf: baseline benchmark and estimate coefficients`

### Task 6: `archmap analyze --estimate`

**Files:**
- Create: `src/archmap/core/perf/estimate.py`
- Modify: `src/archmap/cli/args.py` (analyze parser), `src/archmap/cli/commands.py` (`run_analyze`)
- Test: `tests/test_estimate.py`

**Interfaces:**
- Consumes: `coefficients.json` (Task 5), `discover_source_files` (`utils/file_utils.py`).
- Produces:
  - `calibrate() -> float`: runs `parse_project` on 100 in-memory files from `generate_project`'s python/layered content via `virtual_files`, returns `measured / reference.calibrationSeconds`. Bounded: if it ran > 0.5 s it stops after what it has done and scales.
  - `estimate_project(root: Path, config: dict, *, speed_factor: float | None = None) -> Estimate` where `Estimate = TypedDict("Estimate", {"files": int, "bytes": int, "byLanguage": dict[str, int], "seconds": {"low": float, "expected": float, "high": float}, "peakMb": float, "speedFactor": float, "reductionsUnderBudget": list[str]})`.
  - CLI: `--estimate` flag. Text output (exact copy):

```text
[estimate] 12,345 source files (python 9,001 · typescript 3,344), 81.2 MB
[estimate] expected time: 38 s (range 19 s – 1 min 16 s) on this machine
[estimate] expected peak memory: ~410 MB
[estimate] no analysis was run. Remove --estimate to analyze.
```

  With `--time-budget`, one more line per stage that would be reduced: `[estimate] with --time-budget 30: centrality would run sampled`. `--format json` prints the `Estimate` object to stdout and nothing else. Exit 0; no cache write.

- [ ] **Step 1: Failing tests:** empty dir → `files == 0`, `seconds.expected == 0`, exit 0; json mode stdout parses with `json.loads`; on a 2,000-file `layered` project the measured `analyze_project` wall time is within `[low * 0.5, high * 2]` (generous margin for shared CI runners); `speed_factor=2.0` doubles `expected`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `estimate.py` and the CLI branch at the top of `run_analyze`.**
- [ ] **Step 4: Run, expect PASS; run `archmap analyze . --estimate` on ArchMAP and compare to a real run.**
- [ ] **Step 5: Commit** — `feat(cli): analyze --estimate`

### Task 7: Soft time budget, reductions, cache rules

**Files:**
- Create: `src/archmap/core/perf/budget.py`
- Modify: `src/archmap/config.py` (`[analysis.limits]`), `src/archmap/core/__init__.py` (`analyze_project`), `src/archmap/core/analyzer/dependency_graph.py`, `src/archmap/core/analyzer/centrality.py`, `src/archmap/core/analyzer/quality.py`, `src/archmap/cache.py`, `src/archmap/cli/args.py`, `src/archmap/cli/commands.py`
- Test: `tests/test_budget.py`, `tests/test_config.py`, `tests/test_cache.py`

**Interfaces:**
- Consumes: `Estimate`/`estimate_project` (Task 6), `calculate_all_impacts(should_stop=)` (Task 2), `StageTimer` (Task 1).
- Produces:
  - `class Budget`: `Budget(seconds: float | None, *, source: Literal["cli", "config", "mcp-default", "mcp-arg"])`, `remaining() -> float | None`, `exhausted() -> bool`, `allows(stage: str, expected_seconds: float) -> bool`, `record(stage: str, reason: str, detail: str) -> None`, `reductions: list[Reduction]` with `Reduction = {"stage", "reason", "detail"}`.
  - Config: `[analysis.limits] time_budget_seconds = <float>` (default `None`; `0` → `None`; negative → `ConfigError` with message `analysis.limits.time_budget_seconds must be >= 0`).
  - CLI: `--time-budget SECS` (float ≥ 0, argparse type check; overrides config).
  - `analyze_project(..., time_budget: float | None = None, budget_source: str = "cli")` (explicit arg beats config).
  - Reductions: centrality → `samples=64` when not allowed, skipped entirely (metrics say `"skipped"`) when the budget is already exhausted; centrality loop checks `budget.exhausted()` every 16 sources and stops with what it has. Impact → `should_stop=budget.exhausted` (lists dropped, counts exact).
  - `metrics.analysisQuality.reductions: list[Reduction]` and `metrics.analysisQuality.budget: {"seconds", "source"}` when a budget exists.
  - One `QUAL-*` finding per reduction, category `budget_reduction`, severity `low`, message (exact): `"{stage} was reduced by the {seconds:g} s time budget ({source}): {detail}"`, evidence includes `"Change it with --time-budget, [analysis.limits] time_budget_seconds, or 0 for no limit"`.
  - Cache: `compute_fingerprint` includes `REPORT_SCHEMA = 2` and the effective budget; `analyze_project` never calls `save_cached_report` when `reductions` is non-empty.
  - CLI prints to stderr, unless `--quiet`, one line per reduction: `[budget] <same message as the finding>`.

- [ ] **Step 1: Failing tests:** tiny budget (`0.001`) on a 1,000-file project → reductions for `centrality` and `impact`, findings present, report not cached (`load_cached_report` returns `None`); no budget → identical report to Task 2's output and cached; negative config → `ConfigError`; `--time-budget -1` → argparse exit 2; fingerprint differs between budget `None` and `30`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run new + `tests/test_config.py tests/test_cache.py` + full suite, PASS.**
- [ ] **Step 5: Commit** — `feat: soft time budget with visible reductions`

### Task 8: MCP default budget and notice

**Files:**
- Modify: `src/archmap/cli/mcp_server.py` (`_get_analysis`, tool schemas and dispatch for every tool that calls `_get_analysis`)
- Test: `tests/test_mcp_budget.py`

**Interfaces:**
- Consumes: `analyze_project(time_budget=, budget_source=)` (Task 7).
- Produces:
  - `MCP_DEFAULT_TIME_BUDGET = 120.0`.
  - `_get_analysis(project_path: str, time_budget: float | None = None) -> Any`. Effective budget: tool arg `time_budget` (`0` → none) > `.archmap.toml` > `MCP_DEFAULT_TIME_BUDGET`. The in-memory `_cache` key includes the effective budget.
  - Every analysis-backed tool's `inputSchema` gains optional `"time_budget": {"type": "number", "minimum": 0, "description": "Seconds; 0 = no limit. Default 120 (or .archmap.toml)."}`.
  - When the result has reductions, the tool response gains `"notice"` (exact): `"Analysis was reduced by the {seconds:g} s time budget ({source}): {stages}. For a full run pass time_budget=0 or set [analysis.limits] time_budget_seconds in .archmap.toml."` No reductions → no `notice` field (responses identical to today).

- [ ] **Step 1: Failing tests:** monkeypatch the budget to `0.001` via the tool arg → `notice` present and names the stages; `time_budget=0` → no `notice`, full centrality; config budget beats default; existing `tests/test_mcp_server.py` unchanged and passing.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, PASS** (also `tests/test_mcp_tools_v14.py`, `tests/test_agent_plugin.py`).
- [ ] **Step 5: Commit** — `feat(mcp): 120 s default time budget with notice`

### Task 9: Progress with ETA

**Files:**
- Create: `src/archmap/core/perf/progress.py`
- Modify: `src/archmap/core/parser/__init__.py` (progress callback), `src/archmap/core/__init__.py`, `src/archmap/cli/commands.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Consumes: `Estimate` (Task 6), `StageTimer` (Task 1).
- Produces: `class Progress(stream: TextIO, estimate_seconds: float)` with `stage(name: str)`, `advance(done: int, total: int)`, `close()`; prints `\r[archmap] parse 4,210/12,345 · ~25 s left` at most every 0.5 s. `analyze_project(..., progress: Progress | None = None)`; `parse_project(..., on_file_done: Callable[[], None] | None = None)`. CLI enables it only when `sys.stderr.isatty()`, not `--quiet`, and the estimate's `expected` > 5 s.

- [ ] **Step 1: Failing tests:** with a `StringIO` stream, output contains `parse` and `left`; CLI with non-TTY stderr (pytest capture) prints no `[archmap]` progress; `--format json` stdout parses as JSON.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, PASS.**
- [ ] **Step 5: Commit** — `feat(cli): progress with ETA on stderr`

### Task 10: Docs, CI regression guard, release notes

**Files:**
- Create: `docs/performance.md`, `scripts/perf_guard.py`
- Modify: `mkdocs.yml` (nav), `docs/cli/analyze.md`, `docs/cli/mcp.md`, the config reference page that documents `[analysis.budgets]`, `CHANGELOG.md` (Unreleased), `docs/roadmap.md` (Next — v1.7.0, and v1.8.0: incremental analysis + Termux numbers), `.github/workflows/ci.yml`
- Test: `tests/test_perf_guard.py`

**Interfaces:**
- Consumes: `benchmarks/baseline.json` (Task 5), `scripts/benchmark.py --json` (Task 1).
- Produces: `scripts/perf_guard.py --baseline benchmarks/baseline.json --files 5000 --shape cycle --max-ratio 2.0` exits 1 with `perf regression: 5000 cycle took X s, baseline Y s (> 2.0x)` when slower, 0 otherwise. Baseline rows carry `machine`; the guard compares against a CI-measured row (`machine.platform` startswith `Linux`), so Task 10 adds one CI-measured row by running the benchmark once in CI and committing it.

- [ ] **Step 1: Failing test:** `perf_guard` with a fake baseline of 0.001 s exits 1 and prints the message; with 1000 s exits 0.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement the guard; add a `perf-guard` job to `ci.yml` (ubuntu-latest, Python 3.13, `paths: src/**`, runs after install). Write `docs/performance.md` with: scenario table (CI on `ubuntu-latest`; desktop / MCP) × 1k/5k/20k/50k, time and peak memory generated from `benchmarks/baseline.json` by `scripts/benchmark.py --markdown` (no hand-typed numbers); how to read `--estimate`; soft budget semantics ("may overshoot by one stage"); MCP default 120 s and how to change it; Termux: "measured numbers come in v1.8.0". Document `--estimate`, `--time-budget`, `[analysis.limits]`, the MCP `time_budget` argument and `notice`, `impactedFilesTruncated`.**
- [ ] **Step 4: `python -m pytest`, `python -m ruff check .`, `python -m mypy src/archmap/ --ignore-missing-imports --exclude "web-ui"`, `mkdocs build --strict` (after copying root docs as `docs.yml` does), `python -m archmap.cli.main analyze src/archmap/ --fail-on-cycles --quiet` — all pass.**
- [ ] **Step 5: Commit** — `docs: performance page, perf guard in CI, changelog`

After Task 10: update `C:/Users/kauag/Documents/ArchMAP-video/PROXIMA-VERSAO.md` (user-visible: the 23 s → new number for 5k, `--estimate`, budget/notice; internal: perf guard), then open the PR with the AI-assistance section.
