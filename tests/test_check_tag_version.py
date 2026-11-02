"""The release guard that rejects a tag cut before the version bump."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from archmap import __version__

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_tag_version.py"
_spec = importlib.util.spec_from_file_location("check_tag_version", SCRIPT)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def test_reads_the_same_version_as_the_package() -> None:
    assert guard.package_version() == __version__


def test_matching_tag_passes() -> None:
    assert guard.check(f"v{__version__}", __version__) is None
    assert guard.main(["prog", f"v{__version__}"]) == 0


def test_stale_tag_fails() -> None:
    # The v1.4.1 / first v1.4.2 failure: tag pushed while the code said 1.4.1.
    error = guard.check("v1.4.2", "1.4.1")
    assert error and "expected tag 'v1.4.1'" in error
    assert guard.main(["prog", "v0.0.0"]) == 1


def test_bad_usage() -> None:
    assert guard.main(["prog"]) == 2
