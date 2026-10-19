# archmap hub-report / Arch line

ArchMAP is the `insight` member of the **Arch line** — independent systems
(Arch Hub, System-PVD, SIMPLE-ArCh, ArchMAP) that see each other through the
[Arch Hub](https://github.com/Kaua-KGzin/System-Arch). Contract:
[`docs/ARCH-LINE.md`](https://github.com/Kaua-KGzin/System-Arch/blob/main/docs/ARCH-LINE.md).

## archmap hub-report

Analyzes a project and publishes its architecture score to the Hub.

```bash
archmap hub-report [path] [--system-id ID] [--hub URL] [--token TOKEN]
                   [--commit SHA] [--ref REF] [--report-url URL]
                   [--dry-run] [--strict] [--json]
```

| Field sent | Source |
|---|---|
| `score`, `grade` | `architecture.health` |
| `files`, `cycles` | `metrics.filesAnalyzed`, `metrics.circularDependencyCount` |
| `findings` | number of unified findings |
| `commit`, `ref` | flags, else `GITHUB_SHA` / `GITHUB_REF_NAME` |

- **id**: `--system-id`, else the `id` in `arch.json` (the Arch line
  manifest), else the directory name as a slug.
- **Hub**: `--hub` or `ARCHHUB_URL`; token: `--token` or `ARCHHUB_TOKEN`
  (global or the system's own token).
- Without a Hub it only prints. On GitHub Actions it always appends the score
  to the step summary.
- An unreachable Hub or a rejected report is a warning; `--strict` makes it
  exit 1.

```text
$ ARCHHUB_URL=http://localhost:8080 archmap hub-report .
[info] archmap: architecture 28/100 (F), 107 files, 2 cycles, 94 findings
[ok] Published to Arch Hub http://localhost:8080 as 'archmap'
```

## In CI

Every repository of the line calls the reusable workflow:

```yaml
jobs:
  architecture:
    uses: Kaua-KGzin/ArchMAP/.github/workflows/arch-line-report.yml@main
    secrets: inherit   # ARCHHUB_URL, ARCHHUB_TOKEN (optional)
```

## In `archmap serve`

With `ARCHHUB_URL` set, `serve` registers itself in the Hub as `archmap`
and sends heartbeats (`ARCHHUB_HEARTBEAT_SECONDS`, default 20). Optional:
`ARCHHUB_TOKEN`, `ARCHHUB_PUBLIC_URL`. An unreachable Hub never affects the
server.
