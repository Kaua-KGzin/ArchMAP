# archmap explain

Prints a simple explanation of the project architecture.

## Usage

```bash
archmap explain [path] [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--json` | off | Print JSON instead of terminal output |
| `--max-groups` | `8` | Maximum number of groups in the simple architecture map |
| `--parallel` | on | Enable parallel file parsing |

## Example

```bash
archmap explain .
```

Typical output:

```text
[explain] Project summary
Style: Domain-Driven / Clean Architecture
[map] Simple architecture view
auth -> users, payments
payments -> gateway
```

Use `explain` when you want a quick, readable overview without opening the web UI.
