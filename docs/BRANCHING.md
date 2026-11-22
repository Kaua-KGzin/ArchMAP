# Branching Strategy

`main` is the only long-lived branch. Every change reaches it through a pull
request that CI must pass, and releases are tags on `main`.

## Branch roles

- `main`: protected by a ruleset; always releasable. Every pull request
  targets it.
- `feat/*`: new features.
- `fix/*`: bug fixes.
- `perf/*`: performance work with no behaviour change.
- `docs/*`: documentation-only changes.
- `release/<version>`: the version-bump pull request for a release (see below).
- `feature/*`: legacy alias of `feat/*`, still accepted by CI.

Branches are short-lived: delete them once their pull request is merged.

## Merge policy

1. Branch from `main` and target `main`.
2. **Do not stack pull requests** (pull request B based on pull request A's
   branch). When A merges, GitHub does not retarget B, so B merges into A's
   old branch and never reaches `main`. If B depends on A, base B on `main`
   anyway, say "merge after #A" in its description, and rebase it once A
   lands.
3. All pull requests must pass CI before merge.
4. Every code change must include or update tests.
5. A user-visible change adds a `CHANGELOG.md` entry under `[Unreleased]`,
   mirrored in `docs/changelog.md`.
6. Pull requests opened or updated by an AI agent fill the "AI assistance &
   supervision" section of the template (see `CLAUDE.md`).

## Release process

1. Open `release/<version>` from `main`. It bumps `__version__` in
   `src/archmap/__init__.py` and renames `[Unreleased]` in both changelogs to
   `[<version>] - <date>`.
2. Run the full quality gate: `ruff`, `mypy`, `pytest`, a smoke analysis, and
   the executable smoke test.
3. Merge it into `main`.
4. Tag the merge commit `v<version>` and push the tag. The `publish`,
   `release` and `docker` workflows build and publish from the tag, and
   `scripts/check_tag_version.py` refuses a tag that does not match the
   package version.
