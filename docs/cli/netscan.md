# archmap netscan

Discovers live hosts and open ports on a network — an nmap-style scanner built into ArchMAP. Pure Python (stdlib-only) by default, so it needs no root and no extra dependencies, which makes it work the same way on a laptop or inside Termux on Android. Optionally delegates to a real `nmap` install for deeper scans.

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

## Options

| Option | Default | Description |
|---|---|---|
| `--ports SPEC` | top 20 common ports | Ports to scan, e.g. `22,80,443` or `1-1024` |
| `--top-ports N` | — | Scan the N most common ports instead of `--ports` |
| `--discover-only` | off | Only discover which hosts are up; skip port scanning |
| `--no-discover` | off | Skip host discovery and port-scan every address directly |
| `--fingerprint` / `--no-fingerprint` | on | Grab service banners on open ports |
| `--use-nmap` | off | Delegate scanning to the system `nmap` binary |
| `--nmap-args ARGS` | — | Extra raw arguments passed through to nmap (only with `--use-nmap`) |
| `--os-detection` | off | Attempt OS fingerprinting via nmap `-O` (requires `--use-nmap` and root) |
| `--timeout SECS` | `1.0` | Per-connection timeout in seconds |
| `--concurrency N` | `200` | Max concurrent connections for discovery/port scanning |
| `--json` | off | Output results as JSON |
| `--out PATH` | — | Write the JSON scan report to a file |

## Examples

```bash
# Discover hosts and scan the top 20 ports on a /24
archmap netscan 192.168.1.0/24

# Scan specific ports on a single host
archmap netscan 192.168.1.10 --ports 22,80,443

# Just find which hosts respond, skip port scanning
archmap netscan 192.168.1.0/24 --discover-only

# Scan a small range with more ports, machine-readable output
archmap netscan 10.0.0.1-50 --top-ports 100 --json

# Skip discovery entirely and port-scan a single known-up host directly
archmap netscan 192.168.1.10 --no-discover --ports 1-1024

# Delegate to a real nmap install for a version/OS-detection scan
archmap netscan 192.168.1.0/24 --use-nmap --nmap-args="-sV"

# Save the report to disk
archmap netscan 192.168.1.0/24 --out scan.json
```

## Output

Both engines print through the same clean, aligned report — `--use-nmap` just fills in more of it (service version/extrainfo, an OS guess, nmap's own scan stats and version) instead of dumping nmap's raw console output.

### Default (human-readable, pure-Python engine)

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

### With `--use-nmap` (and `--os-detection`)

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

`nmapVersion`, `stats`, and each host's `os` field are only populated when `--use-nmap` is used (and `os` only when nmap's OS fingerprinting found a match, which requires `--os-detection` and root).

## How it works

1. **Target parsing** expands the target spec (single host, CIDR, or range) into a flat list of IPs/hostnames.
2. **Host discovery** (unless `--no-discover`) tries an ICMP ping first, then falls back to TCP connect probes on a handful of common ports — ICMP is frequently filtered on real networks, so this keeps discovery working without root.
3. **Port scanning** (unless `--discover-only`) opens a TCP connection to each requested port on each live host, using a thread pool for concurrency.
4. **Fingerprinting** (default on) reads whatever banner the service sends on connect, or issues a minimal `HEAD /` request for known HTTP ports.

With `--use-nmap`, steps 2–4 are replaced by a single call to the system `nmap` binary (`nmap -oX -`), and its XML output — including service product/version/extrainfo, the best OS match (with `--os-detection`), and nmap's own run stats — is parsed into the same report shape used by the pure-Python engine.

## Termux setup

```bash
pkg install python
pip install KG-ARCHMAP
archmap netscan 192.168.1.0/24

# optional, only needed for --use-nmap:
pkg install nmap
```

No root is required for the default pure-Python engine.

## Requirements

Pure-Python engine: none — stdlib only. `--use-nmap` requires `nmap` on `PATH`.
