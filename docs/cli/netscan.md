# archmap netscan

Discovers live hosts and open ports on a network — an nmap-style scanner built into ArchMAP. Two engines share the same clean report format: a system `nmap` install (used automatically when present — nmap is simply a more capable scanner) or a built-in, stdlib-only Python engine that needs no root and no extra dependencies, so it works the same way on a laptop or inside Termux on Android.

!!! warning "Authorized use only"
    Only scan networks and hosts you own or are explicitly authorized to test. Unauthorized scanning may be illegal in your jurisdiction.

## Usage

```bash
archmap netscan <target> [options]
```

## Arguments

| Argument | Description |
|---|---|
| `target` | Host/IP, hostname, CIDR block, or range to scan. Comma-separate multiple targets. |

Accepted target formats:

| Format | Example |
|---|---|
| Single IP or hostname | `192.168.1.10`, `example.com` |
| CIDR block | `192.168.1.0/24` |
| Full range | `192.168.1.1-192.168.1.50` |
| Shorthand range | `192.168.1.1-50` |
| Comma-separated combination | `192.168.1.10,192.168.1.0/28` |

## Engine selection

| Flag | Behavior |
|---|---|
| *(none)* | Auto: use `nmap` if it's installed, otherwise the built-in Python engine |
| `--use-nmap` | Require the nmap engine; error out if `nmap` isn't on `PATH` |
| `--no-nmap` | Force the built-in Python engine even if `nmap` is installed |

## Options

| Option | Default | Description |
|---|---|---|
| `--ports SPEC` | top 20 common ports | Ports to scan, e.g. `22,80,443` or `1-1024` |
| `--top-ports N` | — | Scan the N most common ports instead of `--ports` |
| `--discover-only` | off | Only discover which hosts are up; skip port scanning |
| `--no-discover` | off | Skip host discovery and port-scan every address directly |
| `--fingerprint` / `--no-fingerprint` | on | Grab service banners on open ports (Python engine only) |
| `--use-nmap` / `--no-nmap` | auto | See [Engine selection](#engine-selection) |
| `--nmap-args ARGS` | — | Extra raw arguments passed through to nmap (nmap engine only) |
| `--os-detection` | off | Attempt OS fingerprinting via nmap `-O` (nmap engine + root required) |
| `--timeout SECS` | `1.0` | Per-connection timeout in seconds |
| `--concurrency N` | `200` | Max concurrent connections for discovery/port scanning (Python engine only) |
| `--json` | off | Output results as JSON |
| `--out PATH` | — | Write the JSON scan report to a file |

## Examples

```bash
# Discover hosts and scan the top 20 ports on a /24 (nmap if installed, Python otherwise)
archmap netscan 192.168.1.0/24

# Scan specific ports on a single host
archmap netscan 192.168.1.10 --ports 22,80,443

# Just find which hosts respond, skip port scanning
archmap netscan 192.168.1.0/24 --discover-only

# Scan a small range with more ports, machine-readable output
archmap netscan 10.0.0.1-50 --top-ports 100 --json

# Skip discovery entirely and port-scan a single known-up host directly
archmap netscan 192.168.1.10 --no-discover --ports 1-1024

# Pass extra flags through to nmap for a version-detection scan
archmap netscan 192.168.1.0/24 --nmap-args="-sV"

# Force the built-in scanner even though nmap is installed
archmap netscan 192.168.1.0/24 --no-nmap

# Save the report to disk
archmap netscan 192.168.1.0/24 --out scan.json
```

## Output

Both engines print through the same clean, aligned report — nmap just fills in more of it (service version/extrainfo, an OS guess, nmap's own scan stats and version) instead of dumping its own raw console output.

### Python engine (auto-selected when nmap isn't installed, or `--no-nmap`)

```text
Network Scan — target: 192.168.1.0/24 (engine: python)
hosts probed: 254 | hosts up: 3 | duration: 4.82s

192.168.1.1 (router.local) ------------------------------------ UP
    PORT      STATE    SERVICE          INFO
    ----------------------------------------
    22/tcp    open     ssh              SSH-2.0-OpenSSH_9.0
    80/tcp    open     http             HTTP/1.1 200 OK

192.168.1.14 ---------------------------------------------------- UP
    (no open ports found)

Summary: 3 host(s) up, 2 open port(s) total.
```

### nmap engine (auto-selected when installed, with `--os-detection`)

```text
Network Scan — target: 192.168.1.0/24 (engine: nmap v7.94)
hosts probed: 254 | hosts up: 2 | nmap elapsed: 11.80s | duration: 12.40s

192.168.1.1 (router.local) ------------------------------------ UP
    OS: Linux 5.X (92%)
    PORT      STATE    SERVICE          INFO
    ----------------------------------------
    22/tcp    open     ssh              OpenSSH 9.0 protocol 2.0
    80/tcp    open     http             nginx 1.18.0

Summary: 2 host(s) up, 2 open port(s) total.
```

### JSON (`--json`)

```json
{
  "target": "192.168.1.0/24",
  "engine": "nmap",
  "nmapVersion": "7.94",
  "hostsScanned": 254,
  "discoverOnly": false,
  "durationSeconds": 12.4,
  "stats": {"elapsedSeconds": 11.8, "hostsUp": 2, "hostsDown": 252},
  "hosts": [
    {
      "ip": "192.168.1.1",
      "hostname": "router.local",
      "status": "up",
      "os": "Linux 5.X (92%)",
      "openPorts": [
        {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh", "banner": "OpenSSH 9.0 protocol 2.0"}
      ]
    }
  ]
}
```

`nmapVersion`, `stats`, and each host's `os` field are only populated when the nmap engine ran (and `os` only when nmap's OS fingerprinting found a match, which requires `--os-detection` and root). The `engine` field always reflects what actually ran, which matters when the choice was automatic.

## How it works

1. **Target parsing** expands the target spec (single host, CIDR, or range) into a flat list of IPs/hostnames.
2. **Engine resolution**: if `--use-nmap`/`--no-nmap` wasn't passed, ArchMAP checks whether `nmap` is on `PATH` and uses it if so; otherwise (or with `--no-nmap`) it falls back to the built-in engine.
3. Built-in engine only — **host discovery** (unless `--no-discover`) tries an ICMP ping first, then falls back to TCP connect probes on a handful of common ports — ICMP is frequently filtered on real networks, so this keeps discovery working without root.
4. Built-in engine only — **port scanning** (unless `--discover-only`) opens a TCP connection to each requested port on each live host, using a thread pool for concurrency, with optional banner grabbing.

When the nmap engine is used, steps 3–4 are replaced by a single call to the system `nmap` binary (`nmap -oX -`), and its XML output — including service product/version/extrainfo, the best OS match (with `--os-detection`), and nmap's own run stats — is parsed into the same report shape used by the built-in engine.

## Termux setup

```bash
pkg install python
pip install KG-ARCHMAP
archmap netscan 192.168.1.0/24

# optional, to use the nmap engine instead of the built-in one:
pkg install nmap
```

No root is required for the built-in Python engine. `--os-detection` needs root even with nmap installed.

## Requirements

Built-in engine: none — stdlib only. nmap engine (auto-selected when present, or forced with `--use-nmap`) requires `nmap` on `PATH`.
