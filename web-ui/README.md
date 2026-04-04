# web-ui

This folder contains the Node.js development server for local UI exploration.

Contents:

- `server.js`: lightweight Express server that exposes the ArchMAP REST API and serves the frontend
- `dev-server.js`: convenience entry point that runs `server.js` against the local Python analysis engine

## Static assets

The UI assets (`app.js`, `i18n.js`, `index.html`, `styles.css`) live exclusively in:

```
src/archmap/web-ui/static/
```

This is the **single source of truth** for both:

- The dev server (`npm run serve:web`)
- The distributable Python package / standalone executable

## Development workflow

```bash
npm run serve:web
# http://localhost:3000
```

No asset copy or sync step is needed. `dev-server.js` and `server.js` both resolve the `staticDir` to `src/archmap/web-ui/static/` automatically.
