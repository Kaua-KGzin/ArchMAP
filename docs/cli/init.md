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

## Examples

```bash
archmap init
archmap init . --dry-run
archmap init ./my-project
archmap init . --force
```

## Output

The command writes a starter `.archmap.toml` file to the project root.

If the file already exists and `--force` is not supplied, the command exits with
code `1` and prints an error message.
