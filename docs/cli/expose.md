# archmap expose

Correlates open network ports/services (via the built-in netscan engine)
with your codebase's dependency graph: for each open port whose service has
a known client library, finds the matching package dependency in your code
and surfaces its already-computed blast radius. Answers "this open port —
does my code depend on it, and what breaks if it's compromised?"

!!! warning "Authorized use only"
    Only scan networks and hosts you own or are explicitly authorized to test. Unauthorized scanning may be illegal in your jurisdiction.

## Usage

```bash
archmap expose <target> [path] [options]
```

`target` accepts the same formats as [`archmap netscan`](netscan.md) (single
host, CIDR, range, comma-separated combination), and every netscan option
(`--ports`, `--top-ports`, `--use-nmap`/`--no-nmap`, `--scripts`,
`--os-detection`, `--timeout`, `--concurrency`, ...) is available here too —
`expose` runs a full netscan under the hood, then analyzes `path` (project
root, default `.`) and cross-references the two.

## How the correlation works

1. Every open port's `service` name (e.g. `redis`, `postgresql`, `mongodb`)
   is looked up against a curated table of common client-library/import
   names for that service, across ecosystems.
2. If your codebase imports one of those names, it already exists as a
   `pkg:<name>` node in the dependency graph — and every node, package or
   file, already carries a precomputed blast-radius (`impactCount`,
   `impactedFiles`, `risk`) via the same analysis `archmap analyze`/`archmap
   risk` use. No new graph analysis runs; this just cross-references two
   things ArchMAP already computes separately.
3. `expose` also scans the project for literal connection endpoints: URIs
   with a known scheme (`redis://host:6379`, `postgres://user@host:5432/db`)
   and paired `*_HOST`/`*_PORT` config keys (`DATABASE_HOST` /
   `DATABASE_PORT`), across source files, `.env` files, and common config
   formats (`.yml`, `.json`, `.toml`, `.ini`, ...). When one of those
   literally matches the scanned host and port, that's much stronger
   evidence than a service-name-to-import guess.
4. The port's network-side risk rating (from `netscan`'s risk table) and the
   matched package's code-side impact risk are combined into one `severity`
   (`info` → `low` → `medium` → `high` → `critical`). Every open port is
   included as a finding, even with no signal at all, so nothing is
   silently dropped.

This is signal, not a vulnerability scanner: it tells you where network
exposure and code dependency overlap, not whether something is actually
exploitable.

## Confidence scoring

Every finding carries a `confidence` (0.0–1.0) and `confidenceReasons`:

| Signal | Confidence |
|---|---|
| Exact host:port literal found in code, matching service | `0.95` |
| Exact host:port literal found in code, service name disagrees | `0.7` |
| Only a service-name-to-package-import guess (no explicit config found) | `0.4` |
| No signal at all | `0.0` |

## Declared vs. observed: network rules & drift

Declare expected consumer→service relationships in `.archmap.toml`, the same
`"source-tag -> target-tag"` syntax `[architecture.rules]` already uses for
file-to-file boundaries:

```toml
[network.rules]
forbid = ["frontend -> postgresql"]
allow = ["backend -> postgresql"]
```

When a high-confidence match (an exact host:port literal, so ArchMAP knows
*which file* makes the connection) violates a declared rule, `expose` flags
it as a `driftViolation` on that finding, bumps its severity to at least
`high`, and lists it in the top-level `driftViolations` array — this is
"declared architecture" extended to the network boundary: not just "does
`frontend/` import `database/`" but "does `frontend/` talk directly to the
database over the network."

## Examples

```bash
# Scan a host and correlate against the current project
archmap expose 192.168.1.10 .

# Scan a whole subnet against a specific project, JSON output
archmap expose 192.168.1.0/24 ~/projects/my-api --json

# Use the nmap engine with version detection, save the report
archmap expose 192.168.1.10 . --nmap-args="-sV" --out exposure.json
```

## Output

### Default (human-readable)

```text
Exposure Report — target: 192.168.1.10 vs /home/me/my-api
open ports: 2 | matched to code: 1 | high/critical: 1 | drift violations: 1

HOST                  PORT       SERVICE         CONF    SEVERITY
---------------------------------------------------------------------
192.168.1.10           6379/tcp   redis           95%     HIGH
    ! network: Redis is frequently deployed with no authentication
    confidence: exact host:port match found in app/frontend/cache.py
    code: pkg:redis — 12 file(s) depend on it (risk: critical)
    ✗ drift: frontend -> redis is forbidden but app/frontend/cache.py depends on redis
192.168.1.10           80/tcp     http            0%      INFO

Summary: 2 open port(s), 1 matched to code, 1 high/critical.
```

### JSON (`--json`)

```json
{
  "target": "192.168.1.10",
  "projectRoot": "/home/me/my-api",
  "findings": [
    {
      "host": "192.168.1.10",
      "hostname": null,
      "port": 6379,
      "protocol": "tcp",
      "service": "redis",
      "networkRisk": {
        "level": "high",
        "reason": "Redis is frequently deployed with no authentication"
      },
      "matchedPackages": [
        {
          "package": "redis",
          "nodeId": "pkg:redis",
          "impactCount": 12,
          "impactedFiles": ["app/cache.py", "..."],
          "risk": "critical"
        }
      ],
      "confidence": 0.95,
      "confidenceReasons": ["exact host:port match found in app/frontend/cache.py"],
      "driftViolation": {
        "source": "app/frontend/cache.py",
        "target": "redis",
        "kind": "forbid",
        "rule": "frontend -> redis",
        "message": "frontend -> redis is forbidden but app/frontend/cache.py depends on redis"
      },
      "severity": "critical"
    }
  ],
  "driftViolations": ["<same objects as the matching findings' driftViolation>"],
  "summary": {
    "openPorts": 2,
    "matchedToCode": 1,
    "highSeverity": 1,
    "driftViolations": 1
  }
}
```

## Requirements

Same as [`archmap netscan`](netscan.md) (stdlib-only Python engine by
default, or the nmap engine when installed) plus whatever
[`archmap analyze`](analyze.md) needs for the target codebase — no extra
dependencies beyond those two.
