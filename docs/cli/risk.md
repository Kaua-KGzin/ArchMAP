# archmap risk

Inspects the architectural risk of a single file.

## Usage

```bash
archmap risk <file> [path] [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--json` | off | Print JSON instead of terminal output |
| `--max-impacted` | `15` | Maximum impacted files shown in terminal output |
| `--parallel` | on | Enable parallel file parsing |

## Example

```bash
archmap risk src/auth/login.ts .
```

Typical output:

```text
[risk] src/auth/login.ts
Risk score: 84
Signals: cycle, hub
Incoming dependencies: 2
Outgoing dependencies: 3
Blast radius: 5 file(s)
```

Use `risk` before touching a file that looks central, unstable, or suspicious.
