# Contributing

Thanks for contributing to ArchMAP.

## Prerequisites

- Node.js >= 20
- npm >= 10

## Setup

```bash
npm install
```

## Development workflow

1. Create a branch from `main`.
2. Implement your change with tests.
3. Run validation:

```bash
npm run check
```

4. Open a pull request using the project PR template.

## Code guidelines

- Keep changes focused and scoped.
- Preserve CLI compatibility when possible.
- Add or update tests for parser/analyzer/export logic changes.
- Update `README.md`, `CHANGELOG.md`, and `ROADMAP.md` when behavior changes.