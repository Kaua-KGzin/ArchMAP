# archmap improve

Suggests a cleaner project structure automatically.

## Usage

```bash
archmap improve [path] [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--json` | off | Print JSON instead of terminal output |
| `--max-groups` | `8` | Maximum suggested architecture groups |
| `--out-script` | unset | Write a helper refactor script with move commands |
| `--parallel` | on | Enable parallel file parsing |

## Example

```bash
archmap improve . --out-script .codeatlas/refactor.ps1
```

Typical output:

```text
[improve] Automatic architecture suggestions
Suggested architecture groups: /auth, /payments, /users.
Suggested file moves:
  - src/auth/login.ts -> auth/login.ts
  - src/payments/payment.ts -> payments/payment.ts
```

The command does not refactor files automatically. It produces suggestions first,
and the optional script is a helper for review-driven refactors.
