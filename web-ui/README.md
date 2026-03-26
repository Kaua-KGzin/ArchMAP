# web-ui (development copy)

This folder exists for local frontend development with the Node-based dev server.

Contents:

- `server.js`: lightweight Node server used for local UI/API exploration
- `dev-server.js`: convenience entry point for development workflows
- `static/`: development copy of the UI assets

Packaging note:

- The distributable Python package serves the copy under `src/archmap/web-ui/static/`
- `tests/test_web_ui_assets.py` keeps `web-ui/static/` and `src/archmap/web-ui/static/` identical

Why this is duplicated:

- Root `web-ui/` keeps the Node development workflow simple
- `src/archmap/web-ui/` keeps wheel/executable packaging self-contained

If the project later converges on a single asset location, both the dev server and
packaging flow should migrate together.
