# archmap network

Works with **stored network snapshots** — the network-side counterpart to
[`archmap diff`](diff.md). Where `diff` answers "what changed in the code
since the last commit", `archmap network diff` answers "what opened, closed,
or drifted on the network since the last scan".

## The snapshot store

[`archmap netscan`](netscan.md) and [`archmap expose`](expose.md) are
fire-and-forget by default: every run re-scans from scratch and nothing is
kept. Pass `--snapshot` to also persist the report:

```bash
archmap expose 192.168.1.0/24 . --snapshot
```

The report is stored verbatim under `<path>/.archmap/network/`, one JSON
file per scan, named so a lexicographic sort is also a chronological sort:

```text
.archmap/network/
  20260801T120000Z-192-168-1-0-24.json
  20260813T120000Z-192-168-1-0-24.json
```

Same `.archmap/` convention [`archmap memory`](memory.md) writes into, so a
project still needs only one generated-artifacts directory to gitignore (or
commit — a committed history of network snapshots gives you a network
changelog in `git log`).

`--snapshot` is opt-in on purpose: a scan writing files into your project by
default would be a surprise, and only someone who wants diff history needs
the store. The 30 newest snapshots are kept; older ones are pruned on each
save.

!!! warning "Snapshots contain network topology"
    A snapshot records hosts, hostnames, open ports, service banners, and —
    for `expose` — which of your files connect where. Treat the directory
    like any other infrastructure inventory before committing it to a public
    repository.

## `archmap network list`

```bash
archmap network list [path] [--json]
```

Lists stored snapshots, newest first, with the index you can feed back to
`diff`:

```text
Network snapshots — /home/me/my-api/.archmap/network (newest first)

#   CAPTURED                  KIND      TARGET
----------------------------------------------
0   2026-08-13T12:00:00Z      expose    192.168.1.0/24
1   2026-08-01T12:00:00Z      netscan   192.168.1.0/24
```

## `archmap network diff`

```bash
archmap network diff [path] [--from REF] [--to REF] [options]
```

| Option | Default | Description |
|---|---|---|
| `--from REF` | `previous` | Baseline snapshot |
| `--to REF` | `latest` | Snapshot compared against the baseline |
| `--json` | off | Machine-readable diff on stdout |
| `--out PATH` | — | Write the JSON diff to a file |
| `--fail-on-new-ports` | off | Exit `1` when any port opened since the baseline (CI gate) |

A `REF` is `latest`, `previous`, an age index (`0` is the newest, `2` the
third newest — the `#` column from `network list`), or a path to a snapshot
file.

### What it compares

`netscan` and `expose` produce differently-shaped reports (a host/port tree
vs. a flat correlated findings list), so both are first normalized into one
observation per `host:port/protocol`. That means a `netscan` snapshot and an
`expose` snapshot of the same target diff cleanly against each other, and
the diff reports:

- **Ports opened / closed** — present in one snapshot but not the other.
- **Service changes** — a port that stayed open now fingerprints as a
  different service.
- **Risk changes** — that port's risk level moved (e.g. `null` → `high`).
- **Hosts appeared / disappeared** — including hosts that are up with no
  open ports at all.
- **Drift violations new / resolved** — `[network.rules]` violations from
  two `expose` snapshots, keyed by source/target/rule so a re-ordered list
  isn't reported as churn.

### Examples

```bash
# Since the previous scan (the default)
archmap network diff .

# Since a specific point in history
archmap network diff . --from 5 --to latest

# Compare two snapshot files directly
archmap network diff . --from ./before.json --to ./after.json

# CI gate: fail the build if anything opened since the baseline
archmap expose 10.0.0.0/24 . --snapshot
archmap network diff . --fail-on-new-ports
```

### Output

```text
Network Diff — 192.168.1.0/24 → 192.168.1.0/24
baseline: 2026-08-01T12:00:00Z (netscan)
current:  2026-08-13T12:00:00Z (expose)

Hosts appeared (1)
  - 192.168.1.30 (new.local)

Ports opened (1)
  - 192.168.1.10 (db.local) 6379/tcp redis  [HIGH RISK]

Ports closed (1)
  - 192.168.1.10 (db.local) 22/tcp ssh

Risk changes (1)
  - 192.168.1.10 5432/tcp: riskLevel medium → high
```

### JSON (`--json`)

```json
{
  "from": {"kind": "netscan", "target": "192.168.1.0/24", "capturedAt": "2026-08-01T12:00:00Z"},
  "to": {"kind": "expose", "target": "192.168.1.0/24", "capturedAt": "2026-08-13T12:00:00Z"},
  "hostsAppeared": [{"host": "192.168.1.30", "hostname": "new.local"}],
  "hostsDisappeared": [],
  "portsOpened": [
    {
      "host": "192.168.1.10",
      "hostname": "db.local",
      "port": 6379,
      "protocol": "tcp",
      "service": "redis",
      "riskLevel": "high",
      "severity": "high",
      "confidence": 0.95,
      "drift": "frontend -> redis is forbidden but app/cache.py depends on redis"
    }
  ],
  "portsClosed": [],
  "serviceChanges": [],
  "riskChanges": [
    {
      "host": "192.168.1.10",
      "hostname": "db.local",
      "port": 5432,
      "protocol": "tcp",
      "field": "riskLevel",
      "from": "medium",
      "to": "high"
    }
  ],
  "driftViolationsNew": [],
  "driftViolationsResolved": [],
  "summary": {
    "portsOpened": 1,
    "portsClosed": 0,
    "serviceChanges": 0,
    "riskChanges": 1,
    "hostsAppeared": 1,
    "hostsDisappeared": 0,
    "driftViolationsNew": 0,
    "driftViolationsResolved": 0,
    "changed": true
  }
}
```

`severity`, `confidence`, and `drift` are `null` for observations that came
from a bare `netscan` snapshot — only `expose` computes them.

## Python API

```python
from archmap.core.exposure import (
    diff_network_snapshots,
    latest_snapshot,
    list_snapshots,
    resolve_snapshot,
    save_snapshot,
)

save_snapshot(".", expose_report)
before = resolve_snapshot(".", "previous")
after = resolve_snapshot(".", "latest")
print(diff_network_snapshots(before, after)["summary"])
```

## See also

- [`archmap memory`](memory.md) — folds the latest stored snapshot into the
  digest AI coding agents read at session start.
- [`archmap expose`](expose.md) — produces the correlated snapshots this
  command diffs.
