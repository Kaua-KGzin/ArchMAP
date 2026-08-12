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
3. The port's network-side risk rating (from `netscan`'s risk table) and the
   matched package's code-side impact risk are combined into one `severity`
   (`info` → `low` → `medium` → `high` → `critical`). Every open port is
   included as a finding, even with no signal at all, so nothing is
   silently dropped.

This is signal, not a vulnerability scanner: it tells you where network
exposure and code dependency overlap, not whether something is actually
exploitable.

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
open ports: 2 | matched to code: 1 | high/critical: 1

HOST                  PORT       SERVICE         SEVERITY
-----------------------------------------------------------
192.168.1.10           6379/tcp   redis           HIGH
    ! network: Redis is frequently deployed with no authentication
    code: pkg:redis — 12 file(s) depend on it (risk: critical)
192.168.1.10           80/tcp     http            INFO

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
      "severity": "critical"
    }
  ],
  "summary": {"openPorts": 2, "matchedToCode": 1, "highSeverity": 1}
}
```

## Requirements

Same as [`archmap netscan`](netscan.md) (stdlib-only Python engine by
default, or the nmap engine when installed) plus whatever
[`archmap analyze`](analyze.md) needs for the target codebase — no extra
dependencies beyond those two.
