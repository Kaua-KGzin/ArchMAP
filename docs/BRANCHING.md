# Branching Strategy

## Branch roles

- `main`: stable releases only.
- `dev`: integration branch for upcoming release.
- `feature/*`: one new feature per branch.
- `fix/*`: bug fixes.
- `docs/*`: documentation-only changes.
- `release/*`: release candidates and hardening.

## Expected flow

`feature/*` -> `dev` -> `release/*` -> `main`

## Rules

1. Do not merge experimental code directly into `main`.
2. `release/*` accepts only stabilization changes (bug fixes, tests, docs).
3. Every feature branch must include tests.
4. Pull requests should pass CI before merge.
