# Predictable cost at scale: measured, estimated, bounded

- **Status:** approved by the supervisor on 2026-11-26 (Termux row deferred to v1.8.0)
- **Date:** 2026-11-26
- **Target release:** v1.7.0 (headline item)
- **Supervisor:** @Kaua-KGzin

## Intent

A user about to run ArchMAP on a large repository should know, before running
it, roughly how long it will take and how much memory it will use, and the
run should never blow up. Today neither is true. The supervisor's words: make
the expected time for each scenario clear, and improve what can be improved.

Measured on 2026-11-26 (`scripts/benchmark.py`, synthetic Python project,
each file importing 5 neighbours with wrap-around, Windows desktop, CPython
from the repo `.venv`):

| Files | Time | Files/s |
| --- | --- | --- |
| 1,000 | 0.33 s | 3,061 |
| 2,000 | 4.6 s | 431 |
| 5,000 | 23.2 s | 215 |

A 1k/5k/20k run did not finish in 10 minutes. Doubling the file count
multiplies the time by ~14; the curve is roughly quadratic.

A cProfile of the 2,000-file run (15.1 s under the profiler):

| Stage | Cumulative | Note |
| --- | --- | --- |
| `analyze_graph` (`core/analyzer/dependency_graph.py:31`) | 10.3 s | |
| ↳ `calculate_impact` × 2,000 (`core/analyzer/impact_analyzer.py:19`) | 7.8 s | one full BFS per node, and the whole transitive set is stored per node |
| ↳ `betweenness_centrality` (`core/analyzer/centrality.py:42`) | 1.7 s | already bounded (`DEFAULT_SAMPLES = 256`) |
| `parse_project` (`core/parser/__init__.py:72`) | 3.3 s | `ThreadPoolExecutor`, CPU-bound, so the GIL limits it; `normalize_file_id` alone is 2.5 s cumulative |

The root cause of the blow-up is `node["impact"]["impactedFiles"]`: every node
carries the sorted list of every file it transitively impacts. That is
O(V·(V+E)) time and O(V²) **memory and report size**. The synthetic graph is a
single big cycle (worst case: everything impacts everything), but the growth
rate is the same on real graphs with large strongly connected components.

## Goals

1. **Fix the super-linear stages** so analysis time grows close to linearly
   with files + import edges, and memory stays bounded.
2. **A real benchmark suite** at 1k / 5k / 20k / 50k files, more than one
   language, more than one graph shape, measuring time **and** peak memory
   per stage.
3. **Published expectations per scenario** in the docs: a table of expected
   time and memory by repository size for CI (GitHub Action), the MCP server /
   agent use, and Termux (phone).
4. **`archmap analyze --estimate`**: discovers files (cheap) and prints the
   expected time and memory for *this* repository, without analysing it.
5. **A configurable limit** (`--time-budget SECS`, `[analysis.limits]` in
   `.archmap.toml`): when the expensive stages would exceed it, they run in a
   reduced (sampled / capped) mode and the report says so, instead of
   hanging.
6. **Progress with ETA** on stderr for long runs.
7. **A CI regression guard**: a benchmark job that fails when a fixed-size
   run gets markedly slower than a stored baseline.

## Non-goals

- Measured Termux numbers (v1.8.0).
- Incremental analysis (re-analyse only changed files). That is the planned
  v1.8.0 headline and builds on this work.
- Changing what the analysis *means*: risk scores, findings and health on a
  repository that fits the budget must not change.
- New languages or reverse-engineering formats (other v1.7.0 items, planned
  separately).

## Anti-goals (would make this a failure even if it "works")

- An estimate that is confidently wrong: it must show a range and be checked
  against measured runs in the test suite.
- Silent degradation: any sampled or capped stage must be visible in the
  report (`metrics.analysisQuality` and a `QUAL-*` finding) and in the CLI
  output.
- Breaking consumers of the JSON report. Field names stay; new fields are
  additive.

## Approaches considered

1. **Measure, publish, fix the hot spots.** Benchmark suite, docs table, CI
   guard, impact fix. Smallest; ends the blow-up, but users only learn the cost
   by reading docs.
2. **(1) + estimate before running + configurable limit + progress/ETA.**
   Medium. Gives real predictability: known before, never explodes.
3. **(2) + incremental analysis.** Biggest win for CI and agents, but on its
   own it is a release-sized project and needs (2) to be solid first.

**Picked: 2** (supervisor, 2026-11-26). Incremental goes to v1.8.0.

## Design

### Impact analysis (the main fix)

- Compute strongly connected components once (the cycle detector already
  walks the graph; reuse or add Tarjan). Every node in an SCC has the same
  impact set (the SCC itself minus the node, plus everything downstream of
  it), so compute impact on the condensed DAG, then expand.
- `impactCount` stays **exact** for every node (DAG reachability counts over
  the condensation; for very large DAGs, bitsets via Python `int` are an
  acceptable implementation).
- `impactedFiles` is capped at `IMPACT_LIST_CAP` entries (builder's call on the
  value; 200 is a reasonable default), sorted as today. **The cap is always on,
  budget or not** (agent's call: the O(V²) report size is the blow-up, so the
  fix must reach everyone). When capped, the node gets
  `impact.impactedFilesTruncated: true`. Additive field; `types.py` is
  updated. Nodes impacting ≤ cap files are byte-identical to today.
- The full list is still available on demand: the MCP `impact_analysis` tool,
  `reporting.py` and `core/exposure/correlate.py` compute a single-node BFS
  from the edges when the stored list is truncated (one BFS is cheap, and
  `expose` only does it for the few matched packages). So `expose` output and
  the MCP tool's output stay identical to today (agent's call).
- `risk` thresholds are computed from `impactCount`, so they don't change.

### Parsing

- Profile and fix `normalize_file_id` (2.5 s cumulative for 2,000 files:
  likely repeated path normalisation; memoise per run).
- Builder evaluates a `ProcessPoolExecutor` for parsing (CPU-bound work under
  the GIL). Keep threads where process start-up costs more than it saves
  (small repos, Termux); choose by file count.

### Benchmark suite

- Replace / extend `scripts/benchmark.py` (keep its CLI usable) with
  generators for: Python and TypeScript (at least), and graph shapes
  *layered DAG* (typical app), *hub-heavy* (many files importing a few
  utilities) and *one big cycle* (worst case).
- Sizes 1k, 5k, 20k, 50k. Per stage: wall time and peak memory
  (`tracemalloc` or `resource`/`psutil`-free equivalent; no new runtime
  dependency).
- Always runs with `use_cache=False` (the current script relies on the
  default and only discards a warm-up run).
- Writes a machine-readable result (JSON) used by the estimate model and the
  CI guard.

### Estimate model and `--estimate`

- `archmap analyze PATH --estimate` runs discovery only (file count, bytes per
  language) and prints: files, expected time range, expected peak memory, and
  which stages would be reduced under the current limit. Exit 0, no analysis,
  no cache write. `--format json` gives the same as an object.
- The model is a small per-language coefficient table (seconds per file, per
  KB, per edge-estimate) fitted from the benchmark JSON and shipped as data in
  the package, **scaled by a quick machine-speed calibration** (a fixed
  micro-workload of at most ~0.5 s run at estimate time) so the same table
  works on CI, a desktop and a phone (agent's call: one fixed table cannot be
  right on both a desktop and Termux). Builder's call on the exact form; it must be checked by a test
  that runs a mid-size synthetic project and asserts the measured time falls
  inside the predicted range on the CI runner (with a generous margin to avoid
  flakiness).
- Also exposed to agents: the MCP server's analysis entry reports the estimate
  before a long first analysis (builder's call on the exact surface).

### Limits

- `--time-budget SECS` and `[analysis.limits] time_budget_seconds`. Optional
  `max_memory_mb` is a stretch goal.
- Before each expensive stage, the analyzer compares the estimate for that
  stage with the remaining budget. If it would overflow, it runs reduced:
  centrality with fewer samples, impact with the list cap lowered, and so on.
  Parsing is never skipped silently; if parsing alone would overflow, the run
  continues and the report flags it.
- Each reduction is recorded in `metrics.analysisQuality` (which stage, why,
  what was reduced) and produces a `QUAL-*` finding. The CLI prints one line
  per reduction.
- **Scope and strength** (agent's call): the budget covers the whole run's
  wall time. It is a *soft* budget: decided before each expensive stage, plus
  cooperative checks inside the loops that already iterate in steps
  (centrality's sampled sources, impact over the condensation) so they can
  stop early with what they have. Parsing is not cancelled mid-file. The docs
  say "soft budget, may overshoot by one stage", not "hard limit".
- **Cache** (agent's call): a reduced run is never written to the cache, and
  the cache key includes the budget, so reduced data can never be served to a
  later full run. The cache version is bumped because of
  `impactedFilesTruncated`.
- No budget set → full analysis (after the fixes above).
- **Defaults per surface** (supervisor, 2026-11-26):
  - **MCP server:** budget **on** by default (120 s; builder may tune from the
    benchmark), so an agent never hangs on a huge first analysis.
  - **CLI and GitHub Action:** **no** budget by default; a full result matters
    more there, and the Action's job time is already capped by GitHub.
  - **Always tell the user** (supervisor's condition): whenever a default
    budget is active or a reduction happened, the output says so *and says how
    to change it*: the CLI line, the MCP tool response (a plain `notice` field
    the agent can relay, e.g. "analysis reduced by the 120 s default budget;
    set `[analysis.limits] time_budget_seconds` or pass `time_budget=0` for a
    full run"), the `QUAL-*` finding text, and `docs/performance.md`. The MCP
    tools that trigger analysis accept a `time_budget` argument (`0` = no
    limit), and `.archmap.toml` overrides the default for every surface.

### Progress / ETA

- On stderr, only when stderr is a TTY and the run is expected to take more
  than a few seconds: stage name, files parsed / total, ETA from the estimate.
  Never on stdout (JSON output must stay clean). `--quiet` disables it.

### Documentation

- New page `docs/performance.md` (linked from the nav in `mkdocs.yml`): the
  scenario table (CI on `ubuntu-latest`, MCP / local desktop, Termux) with
  sizes 1k–50k, how to read `--estimate`, how limits degrade, and the
  benchmark command to reproduce. Numbers come from the benchmark JSON, not
  hand-typed. The Termux row is **deferred to v1.8.0** (supervisor,
  2026-11-26): v1.7.0 documents CI and desktop/MCP only, and the page says
  Termux numbers come in v1.8.0.
- CLI docs for `--estimate`, `--time-budget`, `--quiet`; config docs for
  `[analysis.limits]`; CHANGELOG; roadmap.

### CI regression guard

- A job (on PRs touching `src/`) runs the benchmark at one fixed size and
  shape and fails if wall time exceeds the stored baseline by a wide margin
  (for example 2×), to catch new quadratic code without being flaky on shared
  runners.

## Constraints

- Python stdlib only for new runtime code (ArchMAP's core has no heavy
  dependencies; Termux must keep working).
- Report output without reductions must be identical to today's except for
  the additive fields and `impactedFiles` lists longer than the cap (golden
  test on ArchMAP itself and the existing fixtures).
- Project rules: new branch + PR, AI-assistance section in the PR, docs in the
  same PR (`mkdocs build --strict`), mypy blocking, ArchMAP self-check.

## Left to the builder

- `IMPACT_LIST_CAP` value, the SCC implementation, process vs thread pool
  thresholds, the estimate model's exact form, and the CI guard's margin,
  within the constraints above.

## Success

- 50k-file synthetic run (layered DAG, Python) finishes on a desktop in
  minutes, not hours, with bounded memory; the 5k worst-case cycle drops from
  23 s to a few seconds.
- `--estimate` on ArchMAP itself and on the benchmark projects lands inside
  its own range.
- `docs/performance.md` answers "how long will this take on my repo" for each
  scenario.
