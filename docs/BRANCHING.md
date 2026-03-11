# Branching Strategy

This repository follows a staged promotion model to protect `main`.

## Branch roles

- `main`: production-ready code only.
- `dev`: integration branch for ongoing work.
- `feat/*`: feature implementation branches.
- `feature/*`: legacy alias supported for compatibility.
- `fix/*`: bugfix branches.
- `docs/*`: documentation-only branches.
- `release/*`: release hardening and final validation.

## Promotion flow

`feat/*` -> `dev` -> `release/*` -> `main`

## Merge policy

1. Never merge `feat/*` directly into `main`.
2. `release/*` accepts only stabilization changes:
   bug fixes, tests, documentation, and release metadata.
3. All pull requests must pass CI before merge.
4. Every code change must include or update tests.
5. Changelog entry is required for user-visible behavior changes.

## Recommended release cadence

1. Open `release/<version>` from `dev`.
2. Freeze feature work in release branch.
3. Run full quality gate:
   `ruff`, `pytest`, smoke analysis, and executable smoke test.
4. Merge `release/<version>` into `main`.
5. Tag and publish release.
6. Back-merge release fixes into `dev`.
