"""Fail when a release tag does not match the package version.

Run by the release workflows before anything is built or published:

    python scripts/check_tag_version.py "$GITHUB_REF_NAME"

``v1.4.2`` must match ``__version__ = "1.4.2"`` in ``src/archmap/__init__.py``.
Without this check a tag cut before the version bump builds the previous
version, and the PyPI step silently skips the upload (``skip-existing``).
Stdlib only, and the package is not imported, so it runs before any install.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "src" / "archmap" / "__init__.py"
VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def package_version(init_file: Path = INIT) -> str:
    match = VERSION_RE.search(init_file.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"error: no __version__ found in {init_file}")
    return match.group(1)


def check(tag: str, version: str) -> str | None:
    """Return an error message, or None when the tag matches the version."""
    expected = f"v{version}"
    if tag != expected:
        return (
            f"error: tag {tag!r} does not match the package version {version!r} "
            f"(expected tag {expected!r}). Bump __version__ (and the manifests "
            "checked by tests/test_versioning.py), merge, then tag that commit."
        )
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_tag_version.py <tag>", file=sys.stderr)
        return 2
    error = check(argv[1], package_version())
    if error:
        print(error, file=sys.stderr)
        return 1
    print(f"ok: tag {argv[1]} matches package version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
