# Installation

## Requirements

- Python `>=3.11`
- pip `>=23`

## Install from PyPI

```bash
pip install archmap
archmap version
```

## Validate before publishing

```bash
python -m pip install -e ".[release]"
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
```

You can smoke test the built wheel locally with:

```bash
pip install --force-reinstall dist/archmap-<version>-py3-none-any.whl
python -m archmap --help
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

On a successful new build, older `dist/archmap-*.exe` files are removed automatically.
