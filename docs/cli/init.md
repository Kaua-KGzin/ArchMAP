# archmap init

Generates a `.archmap.toml` configuration file in a project directory.

`archmap init` inspects the top-level directory structure to infer:

- `ignore_dirs` for folders that should be skipped during analysis
- commented suggestions for `[risks.layer_order]`

## Usage

```bash
archmap init [path] [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--dry-run` | off | Print the generated config to stdout without writing a file |
| `--force` | off | Overwrite an existing `.archmap.toml` |
| `--from-analysis` | off | Analyze the project first and derive layer rules from the actual dependency graph |

## Examples

```bash
archmap init
archmap init . --dry-run
archmap init ./my-project
archmap init . --force

# Derive layer rules from the real dependency graph
archmap init --from-analysis
archmap init --from-analysis --dry-run
```

## Output

The command writes a starter `.archmap.toml` file to the project root.

If the file already exists and `--force` is not supplied, the command exits with
code `1` and prints an error message.

## --from-analysis

When `--from-analysis` is passed, ArchMAP runs a full analysis before generating
the config. It inspects the actual dependency direction between top-level directories:

- Directories with high fan-in and low fan-out rank as more foundational (lower number).
- Any layer violations detected are emitted as `forbid` rules.
- The cycle count is noted as a comment if non-zero.

This produces a richer `.archmap.toml` that reflects the project's real structure
rather than just its folder names.
