# Performance and predictable cost

ArchMAP is meant to cost what you expect on any project size: you can ask for
a prediction before a run, watch progress during it, and cap the time it may
take. This page covers all three, plus the measured numbers.

## Measured numbers

The table below is generated from `benchmarks/baseline.json`, never typed by
hand:

```bash
python scripts/benchmark.py --markdown
```

Each cell is the wall time of one uncached analysis (best of two runs) and the
peak memory of a separate run. Memory is a `tracemalloc` peak of Python
allocations, not the process RSS, so the operating system will report more.

**Scenario: Windows 11 desktop, 12 CPUs, Python 3.14, synthetic projects, no
cache.** This is the only machine measured so far. Rows from the CI runner
(`ubuntu-latest`) and from other machines will be added once they are
measured; until then, do not read these as promises for your hardware. Use
`--estimate`, which calibrates to the machine it runs on.

<!-- generated: python scripts/benchmark.py --markdown -->

| Scenario | 1,000 files | 5,000 files | 20,000 files | 50,000 files |
|---|---|---|---|---|
| python, cycle | 1.3 s / 8 MB | 3.7 s / 40 MB | 17.8 s / 156 MB | 61.6 s / 396 MB |
| python, hub | 0.7 s / 7 MB | 2.6 s / 36 MB | 12.7 s / 178 MB | 38.1 s / 637 MB |
| python, layered | 0.6 s / 5 MB | 2.1 s / 27 MB | 13.2 s / 123 MB | 35.2 s / 424 MB |
| typescript, cycle | 1.2 s / 8 MB | 3.0 s / 40 MB | 16.3 s / 163 MB | 55.0 s / 399 MB |
| typescript, hub | 0.7 s / 7 MB | 2.7 s / 36 MB | 14.2 s / 186 MB | 34.4 s / 641 MB |
| typescript, layered | 0.6 s / 6 MB | 2.3 s / 26 MB | 13.2 s / 131 MB | 42.0 s / 432 MB |

<!-- end generated -->

Shapes: `layered` is a typical layered application, `hub` has a few
heavily-imported modules, and `cycle` is the worst case for impact analysis
(a large strongly connected component). Larger and denser graphs cost more:
the reach sets behind impact analysis can take memory that grows with the
square of the node count (about V&sup2;/8 bits) on very large, deeply layered
graphs, so the 50,000-file rows are the ones to watch.

| Platform | Status |
|---|---|
| Windows desktop (above) | Measured |
| CI, `ubuntu-latest` | Not yet. The CI perf guard checks scaling instead (see below) |
| Termux / Android | Measured numbers come in v1.8.0 |

## Predict a run: `--estimate`

```bash
archmap analyze . --estimate
```

Nothing is analyzed. ArchMAP counts the source files, runs a ~100-file
calibration (at most 0.5 s) to learn how fast this machine is, and prints an
expected time with a range, an expected peak memory, and any reductions a
`--time-budget` would force:

```text
[estimate] 125 source files (python 118 · javascript 7), 1.4 MB
[estimate] expected time: <1 s (range <1 s – <1 s) on this machine
[estimate] expected peak memory: ~1 MB
[estimate] no analysis was run. Remove --estimate to analyze.
```

For scripts, `archmap analyze . --estimate --format json` writes the estimate
as JSON on stdout, and nothing else. (A normal `analyze --format json` writes
the report to the `--out` file, so stdout JSON-only applies to the estimate.)

The estimate is a fit to measured runs and is accurate to roughly a factor of
two. The range is the honest part of it; the worst case is a project made of
large dependency cycles, which costs more per file than the fit assumes.

## Watch a run: progress line

On a terminal, a run that is expected to take more than 5 seconds prints a
progress line on **stderr** with an ETA:

```text
[archmap] parse 4,210/12,345 · ~25 s left
```

It appears only when stderr is a TTY, only when the estimate is over 5 s, and
never with `--quiet`. Pipes, CI logs and the MCP server never get it, so
machine-readable output is unaffected.

## Cap a run: the time budget

```bash
archmap analyze . --time-budget 60
```

```toml
# .archmap.toml
[analysis.limits]
time_budget_seconds = 60
```

`0` means no limit everywhere; a negative value is rejected. Where the budget
comes from, in order of precedence:

| Surface | Order |
|---|---|
| CLI (`analyze`) | `--time-budget` > `[analysis.limits]` in `.archmap.toml` > no limit |
| Other commands (`check`, `watch`, `serve`, ...) | `[analysis.limits]` in `.archmap.toml` > no limit |
| MCP server | tool argument `time_budget` > `[analysis.limits]` > **120 s default** |

The budget is **soft**: parsing is never cut short, and some other stages
never check it, so a run can overshoot. What it does is reduce the optional
precision of the later stages when the run is running out of time:

- **Impact lists are dropped.** `impactCount`, `risk` and cycles stay exact;
  the `impactedFiles` list of the affected files is left empty and the node is
  marked `impactedFilesTruncated: true`.
- **Centrality is sampled** to 64 files, or skipped when no time is left.

Nothing is reduced silently:

- Every reduction becomes a `QUAL-*` finding (category `budget_reduction`)
  that names the stage and how to lift the limit.
- `archmap analyze` also prints a `[budget] ...` line on stderr (not with
  `--quiet`). Other commands that pick up a `.archmap.toml` budget announce it
  only through the `QUAL-*` finding.
- The MCP response carries a `notice` field saying what was reduced and how to
  get a full run.
- `metrics.analysisQuality.budget` and `.reductions` record it in the report.
- A reduced run is never written to the cache, so the next run without the
  budget starts from a full analysis.

### MCP: 120 s by default

The MCP server applies a 120 s budget when nothing else is set, so a
conversation is never stuck behind a huge analysis. Raise it, or lift it, per
call with the `time_budget` argument (`0` = no limit), or for the project in
`.archmap.toml`. Tools that run a full analysis accept `time_budget`; see
[archmap mcp](cli/mcp.md).

## Impact lists and `impactedFilesTruncated`

Stored `impactedFiles` lists are always capped at 200 entries
(`IMPACT_LIST_CAP`), regardless of any budget; `impactCount` and `risk` are
always exact. A capped list is flagged `impactedFilesTruncated: true`. The full
list is computed on demand where you ask for a specific file:

- the MCP `impact_analysis` tool,
- `archmap expose`,
- `archmap risk --json`,
- `archmap analyze --impact PATH`.

## The CI perf guard

`scripts/perf_guard.py` runs in CI on changes under `src/` and fails when
analysis gets slower in a way that matters:

1. **Scaling** (machine independent): analysis of a 4,000-file project must
   take at most 6x as long as 1,000 files (`--max-scaling`). Linear growth is
   about 4x; an accidental quadratic step is about 16x.
2. **Absolute**: compared with the matching row of `benchmarks/baseline.json`
   (`--max-ratio`, default 2.0), only when the file holds a row measured on the
   same platform. Today it holds Windows rows only, so on CI this check prints
   `no same-platform baseline, skipped`. It activates once a CI-measured row is
   committed.

```bash
python scripts/perf_guard.py --baseline benchmarks/baseline.json --files 5000 --shape cycle
```
