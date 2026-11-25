# GitHub Action

ArchMAP ships a composite GitHub Action (`action.yml` at the repository root).
It analyzes the project, can fail the job on quality gates, can upload SARIF
to GitHub Code Scanning, and can post the architecture delta of a pull request
as one comment that it keeps up to date.

## Minimal workflow

```yaml
name: architecture
on:
  pull_request:

permissions:
  contents: read
  pull-requests: write   # only needed for `comment: true`

jobs:
  archmap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: Kaua-KGzin/ArchMAP@v1.6.0
        with:
          comment: "true"
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Project path, relative to the repository root |
| `python-version` | `3.13` | Python used to run ArchMAP |
| `archmap-version` | latest | `KG-ARCHMAP` version from PyPI, or `source` to install the ArchMAP source that ships with the action (code and action always match) |
| `format` | `json` | `json`, `mermaid`, or `both` |
| `out` | `.codeatlas/graph.json` | JSON report path |
| `sarif` | `false` | Export SARIF and upload it to Code Scanning |
| `sarif-path` | `.codeatlas/archmap.sarif` | SARIF path |
| `fail-on-cycles` | `false` | Fail on any circular dependency |
| `fail-on-god-modules` | `false` | Fail on any god module |
| `fail-on-explosions` | `false` | Fail on any dependency explosion |
| `fail-on-custom-rules` | `false` | Fail on `[architecture.rules]` violations |
| `min-health` | `0` | Fail below this health score (0–100) |
| `quiet` | `false` | Suppress banner and insights |
| `comment` | `false` | Post the PR architecture delta (see below) |
| `github-token` | `${{ github.token }}` | Token used to post the comment |

## Outputs

| Output | Description |
|---|---|
| `json-path` | Absolute path to the JSON report |
| `sarif-path` | Absolute path to the SARIF file (empty unless `sarif`) |
| `health-score` | Health score of the head commit |
| `pr-report-path` | Absolute path to the rendered PR report (empty unless `comment` ran) |

## PR comment (`comment: true`)

On `pull_request` events the action also analyzes the PR's **base commit**
(checked out with `git worktree`, analyzed by the same ArchMAP version) and
compares the two reports with
[`archmap diff --snapshot-a/-b --format markdown`](cli/diff.md). The comment shows:

- health score and grade, base → head;
- tested-file ratio, base → head, and files that lost their tests;
- new and resolved findings (matched by a stable key, not by ID);
- files that became structural bottlenecks.

```text
### ArchMAP · architecture delta
Health **68 → 64** (C → D) · ▼ 4 · Tested files **72.9% → 70.1%** · Cycles 3 → 3 · Findings +3 / −1

#### New findings (3)
| Severity | Finding | Where |
| high | Structural bottleneck: src/core/router.ts lies on 31.4% ... | `src/core/router.ts` |
```

How it behaves:

- **One comment per PR.** It finds its previous comment by a hidden marker and
  edits it on every push.
- **Runs even when a gate fails.** If `min-health` or a `fail-on-*` input fails
  the job, the report is still produced, which is when the delta matters most.
- **Never fails the job by itself.** Fork and Dependabot PRs get a read-only
  token: the report goes to the job summary and the step logs a warning.
- **The base uses its own `.archmap.toml`**, so a PR that edits the config shows
  the effect of that edit.
- Reports from ArchMAP 1.5.0 or older carry no findings; the comment then shows
  the health and test numbers and says findings could not be compared.

!!! warning "Do not use `pull_request_target`"
    The action checks out and analyzes the PR's code. Run it on `pull_request`,
    where a fork's token is read-only, not on `pull_request_target`.
