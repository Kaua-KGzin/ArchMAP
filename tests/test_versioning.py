"""Every place that states ArchMAP's version must agree with the package version.

The Python package (`archmap.__version__`, read by hatch for the wheel) is
the single source of truth. Release notes, the docs site, the npm manifests,
the README badge, and the Claude Code plugin all restate it, and they drift
silently unless a test pins them together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from archmap import __version__

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _key(version: str) -> tuple[int, int, int]:
    match = SEMVER.match(version)
    assert match, f"not a semantic version: {version}"
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def test_package_version_is_semver() -> None:
    _key(__version__)


def test_changelog_top_release_is_current_version() -> None:
    releases = RELEASE_HEADING.findall(_read("CHANGELOG.md"))
    assert releases, "CHANGELOG.md has no '## [x.y.z] - YYYY-MM-DD' headings"
    assert releases[0][0] == __version__


def test_changelog_releases_are_strictly_descending() -> None:
    versions = [_key(v) for v, _ in RELEASE_HEADING.findall(_read("CHANGELOG.md"))]
    assert versions == sorted(versions, reverse=True)
    assert len(versions) == len(set(versions)), "duplicate release heading"


def test_docs_changelog_mirrors_root_changelog() -> None:
    assert _read("docs/changelog.md") == _read("CHANGELOG.md"), (
        "docs/changelog.md must be a copy of CHANGELOG.md (cp CHANGELOG.md docs/changelog.md)"
    )


def test_npm_manifests_match() -> None:
    package = json.loads(_read("package.json"))
    lock = json.loads(_read("package-lock.json"))
    assert package["version"] == __version__
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__


def test_plugin_manifest_matches() -> None:
    plugin = json.loads(_read("plugins/archmap/.claude-plugin/plugin.json"))
    assert plugin["version"] == __version__


def test_readme_and_docs_home_state_current_version() -> None:
    readme = _read("README.md")
    assert f"version-{__version__}-brightgreen" in readme
    assert f"| Release | `v{__version__}` |" in readme
    whats_new = _read("docs/index.md").split("## What's new", 1)[1]
    first_entry = re.search(r"- \*\*(\d+\.\d+\.\d+)\*\*", whats_new)
    assert first_entry and first_entry.group(1) == __version__
