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

## Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python
pip install KG-ARCHMAP
```

`archmap analyze`/`serve` reads files directly off the filesystem, so if your
project lives in Android's shared storage (e.g. `Download/`), Termux needs to
actually be able to see it — this trips people up more than anything else on
Android:

1. **Run the storage setup and accept the permission prompt:**
   ```bash
   termux-setup-storage
   ls -la ~/storage/   # should list downloads, dcim, pictures, etc.
   ```
2. **If `~/storage/downloads/<project>` still looks empty** (directories
   exist but contain nothing), Android's separate "All files access"
   permission is the usual culprit — `termux-setup-storage`'s prompt alone
   doesn't always grant it. In Android Settings → Apps → Termux →
   Permissions → Files and media, enable **"Allow management of all
   files"**.
3. **Most reliable fix**: copy the project into Termux's own home directory
   instead of analyzing it in place — this sidesteps Android's scoped
   storage entirely:
   ```bash
   mkdir -p ~/projects
   cp -r ~/storage/downloads/your-project ~/projects/
   archmap serve ~/projects/your-project
   ```

If you point `archmap` at a path that doesn't actually exist (a typo, or a
broken storage symlink), it now fails with a clear
`project path does not exist: ...` error instead of silently reporting "0
files analyzed" as if the scan succeeded — that message is a reliable signal
the path itself is the problem, not your project.

The web UI (`archmap serve`) is responsive and works the same way in a
mobile browser as on desktop — see [Serve](../cli/serve.md).

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
