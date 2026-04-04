# archmap watch

The `watch` command and the `--watch` flag for `serve` keep analysis running
while files change.

## Command: `archmap watch`

Analyzes the project once and then re-runs analysis automatically when source
files change.

### Usage

```bash
archmap watch [path] [options]
```

### Options

| Option | Default | Description |
|---|---|---|
| `--interval` | `2.0` | Polling interval in seconds |
| `--parallel` | on | Enable parallel parsing |

### Output

When a change is detected, ArchMAP prints a small delta summary:

- health score change
- cycle count change
- added or removed file counts

## Command: `archmap serve --watch`

Enables live reload in the interactive web UI.

### Usage

```bash
archmap serve --watch
```

### How it works

1. ArchMAP starts a background watcher.
2. The web UI subscribes to update events.
3. Saving a file triggers re-analysis.
4. The browser refreshes the graph without a full restart.
