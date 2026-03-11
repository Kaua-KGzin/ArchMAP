# Logging and Artifacts

## Logging policy

- Runtime logs belong in `logs/runtime/` (ignored by git).
- Historical troubleshooting logs may be archived in `logs/archive/`.
- Avoid committing machine-specific temporary logs.

## Build artifact policy

- `build/` and `dist/` are generated outputs.
- Do not treat build outputs as source code.
- Publish binaries through release assets, not direct source commits.

## Recommended cleanup

```bash
git clean -fdX
```

Use this only when you understand it will remove ignored generated files.
