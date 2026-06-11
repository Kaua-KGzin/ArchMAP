# Installation

## Requirements

- Python `>=3.11`
- pip `>=23`

## Install from PyPI

```bash
pip install KG-ARCHMAP
archmap version
```

## Optional: tree-sitter parsers

ArchMAP works out of the box with regex-based parsers. For the most accurate
analysis, install the optional `[tree-sitter]` extra, which enables real
AST-based parsing for all 9 languages:

```bash
pip install "KG-ARCHMAP[tree-sitter]"
```

When installed, tree-sitter is used as a resilient **primary** parser — each
grammar loads independently, and any file it cannot parse falls back to the regex
path automatically (it is never dropped). Without the extra, the regex fallback is
used and nothing breaks.

## Docker

```bash
docker run -p 3000:3000 -v "$(pwd):/project" ghcr.io/kaua-kgzin/archmap
```

## Install for development

```bash
git clone https://github.com/Kaua-KGzin/ArchMAP
cd ArchMAP
python -m pip install -e ".[dev]"
```

## Node dependencies (optional, for `web-ui/dev-server.js`)

```bash
npm ci
```

## Windows executable

Download `archmap.exe` from Releases, or build locally:

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -Clean
```

Generated artifacts:

- `dist/archmap.exe`
- `dist/archmap-<version>.exe`
- `dist/archmap-build-info.json`
