# PR report: architecture delta as a sticky pull-request comment

- **Status:** approved by the supervisor on 2026-11-25 (self-test job comments on ArchMAP's own PRs: approved)
- **Date:** 2026-11-25
- **Target release:** v1.6.0
- **Supervisor:** @Kaua-KGzin

## Intent

Show, on every pull request, what the change did to the architecture: health
going up or down, findings it introduced or resolved, files that became
structural bottlenecks, and files that lost their tests. Today ArchMAP's
GitHub Action reports absolute numbers for the head commit only (and can fail
on them); a reviewer cannot see *what this PR changed*.

This is also the visible face of v1.6.0: test mapping and structural
bottlenecks (already on `main`) become something a reviewer sees in the PR,
not only fields in a JSON file.

## Goals

1. One comment per PR, updated in place on every push (no comment spam).
2. Content: health score and grade (base → head), new and resolved findings,
   new structural bottlenecks, files that lost test coverage, tested-file
   ratio (base → head).
3. Reuse the same full analysis `archmap analyze` runs, so the comment matches
   what users get locally.
4. Off by default; zero cost for existing Action users who don't opt in.
5. Usable outside GitHub: the comparison and the Markdown are CLI features.

## Non-goals (this release)

- Failing the build on a *regression* (e.g. `--fail-on-new-findings`). The
  existing `fail-on-*` / `min-health` inputs stay the gate. Possible follow-up.
- Network drift in the comment.
- GitLab / Bitbucket posting (the Markdown works there; posting does not).
- Inline review comments on specific lines.

## Anti-goals (failure even if it "works")

- Commenting on every push as a new comment.
- Failing the user's CI because the comment could not be posted
  (fork PRs have a read-only token).
- Using `pull_request_target` or any setup that runs PR code with a write token.
- Making the Action slower or noisier for users who did not enable it.

## Findings from the codebase (2026-11-25, `main` at `b7130e0`)

1. `archmap diff --snapshot-a A.json --snapshot-b B.json` exists since v0.8.0,
   but **crashes** on the JSON `archmap analyze` exports:
   `AttributeError: 'str' object has no attribute 'get'` in
   `diff_analyzer._file_node_map`. The export writes `nodes`/`edges` as the
   simple id lists and puts full nodes under `detailed`; `diff_reports`
   expects the in-memory shape. No test covers snapshot diffs.
2. `analyze_graph` builds a unified `findings` list (`ARCH-*`, `QUAL-*`,
   `TEST-*`, `GRAPH-*`), but `json_exporter.export_graph_as_json` does not
   write it. Snapshots therefore carry no findings.
3. Finding IDs are sequential per run (`ARCH-001`…), so they cannot match a
   finding across two runs. Natural keys exist for most categories:
   `file` (god_module, dependency_explosion, structural_bottleneck,
   untested_critical_file), `source`+`target` (layer_violation, rule
   violations), category alone (`QUAL-*`). Cycles carry members only inside
   an evidence string.
4. `diff_reports` already computes health delta, cycles, complexity, file and
   edge changes, and risk-count deltas.

## Approaches considered

- **A. Comparator over two full JSON reports (chosen by the supervisor).**
  The Action analyzes the base commit (via `git worktree`) and the PR head
  with the normal `analyze`; `archmap diff --snapshot-a/--snapshot-b` compares
  them and renders Markdown. Same analysis as users run, testable with fixture
  JSON, works outside GitHub. Cost: two analyses in CI (only when enabled).
- B. `archmap pr-report --base <ref>` doing git checkout + analysis + render in
  one Python command. Easier to call, but mixes git plumbing into the
  comparator and is harder to test.
- C. `--markdown` on today's git-ref `diff`. Cheapest, but that path uses a
  reduced analysis (no findings, test mapping or centrality), which removes
  the point.

Refinement after recon: A is built **on the existing `diff --snapshot-a/-b`**
instead of a new `compare` command, so there is one way to compare reports.

## Design

### 1. Snapshot loading (bug fix)

A `load_snapshot(path) -> dict` in the diff module normalizes an exported
report to the in-memory shape: full nodes/edges from `detailed`, the id lists
as `simple`, everything else as is. It also accepts an already in-memory shape
(older or hand-made files). `run_diff` uses it for both snapshots. This fixes
finding 1 on its own and ships even if the rest slips.

### 2. Findings in the JSON export

`export_graph_as_json` writes `findings` (additive field; existing consumers
ignore it). Each finding gains a `key`: a stable fingerprint string.

### 3. Finding key

One helper, `finding_key(finding) -> str`, in `core/analyzer/findings.py`:

- `category|file` when `file` is set;
- `category|source|target` when both are set;
- `category|<members sorted, joined by ",">` for cycles: the cycle builder
  stores the sorted member list in `key` directly instead of it being parsed
  from text;
- `category` otherwise (`QUAL-*`).

The builders set `key` when creating each finding; the helper is the single
definition and is what tests pin down. Messages and evidence never take part
(they contain numbers that drift, e.g. "29.2% of chains").

### 4. Delta

`diff_reports` gains, **only when both reports carry `findings`**:

- `findings`: `new` and `resolved` (full finding objects, matched by `key`;
  new ones listed with the head's ID, resolved ones with the base's), and
  `unchanged` (count).
- `tests`: `baseTestedRatio`, `headTestedRatio`, `lostCoverage` (files with a
  non-empty `testedBy` in base and empty in head, present in both).
- `bottlenecks`: `new` = new findings of category `structural_bottleneck`
  (a convenience view of `findings.new`).

If either report lacks `findings` (snapshot from ≤ v1.5.0), these sections are
omitted and the Markdown says the base report predates finding comparison.
Existing keys of the diff output do not change.

### 5. Markdown rendering

`diff --format {text,json,markdown}` (keeping `--json` as an alias of
`--format json`) and `--out PATH`. The renderer is a pure function
`render_pr_report(diff, *, base_label, head_label) -> str` in
`exporters/pr_report.py`. First line is the hidden marker
`<!-- archmap:pr-report -->`, which the Action uses to find its comment.

Sketch:

```
<!-- archmap:pr-report -->
### ArchMAP · architecture delta
Health **68 → 64** (C → D) · ▼ 4
Tested files **72.9% → 70.1%** · Cycles 3 → 3 · Findings +3 / −1

#### New findings (3)
| Severity | Finding | Where |
| high | Structural bottleneck (31.4% of import chains) | `src/core/router.ts` |
| medium | Layer violation: cli → core | `src/cli/x.ts` → `src/core/y.ts` |
| medium | High-risk file with no test | `src/core/router.ts` |

#### Resolved (1)
| medium | God module | `src/legacy/big.ts` |

#### Lost test coverage (1)
`src/core/router.ts` (was tested by `tests/router.test.ts`)

<sub>ArchMAP 1.6.0 · base `abc1234` → head `def5678`</sub>
```

Each list shows at most 15 rows plus "…and N more"; the whole body is capped
below GitHub's 65,536-character comment limit. A no-change PR renders a single
line: "No architecture changes detected."

### 6. GitHub Action (`action.yml`)

New inputs:

- `comment` (default `"false"`): enable the PR report.
- `github-token` (default `${{ github.token }}`): token used to post.

When `comment == 'true'` and the event is `pull_request`:

1. The existing analysis step runs on the head, as today.
2. `git fetch --depth=1 origin <base.sha>` (the default checkout is shallow),
   then `git worktree add "$RUNNER_TEMP/archmap-base" <base.sha>`.
3. Analyze `$RUNNER_TEMP/archmap-base/<path>` with the same installed ArchMAP,
   writing `base.json`. The same version analyzes both sides, so the delta
   reflects code changes only. The base uses its own `.archmap.toml`.
4. `archmap diff --snapshot-a base.json --snapshot-b head.json --format markdown --out report.md`.
5. Append `report.md` to `$GITHUB_STEP_SUMMARY` (works on forks too).
6. Upsert the comment with `gh api`: list the PR's issue comments, find the
   one whose body starts with the marker, PATCH it, else POST. On any posting
   error (e.g. 403 from a fork's read-only token), emit `::warning::` and
   continue. The step never fails the job.
7. Remove the worktree.

When `comment` is enabled on a non-PR event, the step is skipped with a notice.
Consumers must grant `pull-requests: write`; the docs show the minimal
workflow. No `pull_request_target`.

### 7. Docs and release notes

- `docs/cli/diff.md` (or the existing diff page): snapshots, `--format markdown`.
- Action docs: `comment` / `github-token`, permissions, fork behavior, example.
- `CHANGELOG.md` `[Unreleased]`: Added (PR report, findings in JSON export,
  finding `key`), Fixed (snapshot diff crash).

## Testing

- Unit: `load_snapshot` on an exported report and on an in-memory one;
  `finding_key` per category; cycle key independent of member order.
- Unit: delta with fixture reports (new, resolved, unchanged, lost coverage,
  base without findings).
- Unit: renderer snapshot tests (normal, empty, truncated at 15, size cap).
- Regression: `analyze` → export → `diff --snapshot-a/-b` round trip on the
  sample project (the exact path that crashes today).
- Action: a CI job on this repo's own PRs runs the action with `uses: ./` and
  `comment: true` (it posts on ArchMAP's own PRs), which also gives `action.yml`
  its first CI coverage.

## Constraints

- Python ≥ 3.11, stdlib only (no new runtime deps). Coverage gate 85%. mypy
  and ruff as in CI.
- `gh` is preinstalled on GitHub-hosted runners; self-hosted runners without
  it get the warning path, not a failure.

## Left to the builder

- Exact column wording and emoji-free styling of the Markdown.
- Where `load_snapshot` lives (diff module vs. a small `snapshots` helper).
- Whether `bottlenecks`/`tests` are top-level in the diff output or nested.

## Edge cases settled during review (agent's calls)

- **Base has no `path` directory** (the PR creates the project folder) or the
  base analysis fails: render a head-only report that says the base could not
  be analyzed; never fail the job.
- **Same flags on both sides:** the base analysis reuses the head step's
  analysis options (format/ignore settings from inputs), so only the code
  differs.
- **Dependabot and fork PRs** get a read-only token: they take the
  step-summary-only path with a warning.
- **This repo's own CI** declares `permissions: contents: read` at the top
  (#78); the self-test job adds `pull-requests: write` at job level only.
- **Comment language:** English, like the rest of the project's output.
- **Duplicated markers** (someone copies the marker into another comment):
  update the newest comment authored by the token's user that has the marker;
  never edit comments by other authors.

## Calls made by the agent (to double-check)

- Build on `diff --snapshot-a/-b` rather than a new `compare` command.
- Base analyzed with the base's own `.archmap.toml` (a PR that edits the config
  shows the config's effect in the delta).
- Self-test job posts on ArchMAP's own PRs.
