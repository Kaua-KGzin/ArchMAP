"""On-disk snapshot store for network observations (`netscan` / `expose`).

Network scans were previously fire-and-forget: every run re-scanned from
scratch and there was no way to ask "what changed since last time" the way
`archmap diff` already answers that for code. This module persists a scan
report under the project's `.archmap/network/` directory (the same
generated-artifacts convention `archmap memory` writes into), so
`archmap network diff` can compare two points in time and `archmap memory`
can fold the latest observation into its digest.

Snapshots are plain JSON, one file per scan, named so a lexicographic sort
is also a chronological sort.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

logger = logging.getLogger(__name__)

DEFAULT_NETWORK_SNAPSHOT_DIR = ".archmap/network"

SNAPSHOT_VERSION = 1

# Keeps the store from growing without bound on a machine that scans on a
# schedule. Oldest snapshots are dropped first; 30 is enough history for a
# "what changed this month" question without turning the directory into a
# data set nobody prunes.
DEFAULT_MAX_SNAPSHOTS = 30

SnapshotKind = Literal["netscan", "expose"]

_SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9]+")
_FILENAME_STAMP = "%Y%m%dT%H%M%SZ"


class Snapshot(TypedDict):
    """A persisted scan report plus the metadata needed to diff it."""

    version: int
    kind: str
    target: str
    capturedAt: str
    report: dict[str, Any]


class SnapshotRef(TypedDict):
    """A snapshot's identity without the cost of loading its full report."""

    path: str
    kind: str
    target: str
    capturedAt: str


def snapshot_dir(project_root: str | Path) -> Path:
    """The `.archmap/network/` directory for `project_root` (not created)."""
    return Path(project_root).resolve() / DEFAULT_NETWORK_SNAPSHOT_DIR


def _slugify_target(target: str) -> str:
    slug = _SLUG_UNSAFE.sub("-", target).strip("-").lower()
    return slug[:48] or "scan"


def _detect_kind(report: dict[str, Any]) -> SnapshotKind:
    return "expose" if "findings" in report else "netscan"


def save_snapshot(
    project_root: str | Path,
    report: dict[str, Any],
    *,
    kind: SnapshotKind | None = None,
    captured_at: datetime | None = None,
    max_snapshots: int | None = DEFAULT_MAX_SNAPSHOTS,
) -> Path:
    """Persist `report` as a new snapshot and return the file it was written to.

    `kind` defaults to `"expose"` for a correlated report (one with
    `findings`) and `"netscan"` otherwise. The report is stored verbatim, so
    a snapshot always replays exactly what the scan saw.
    """
    directory = snapshot_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)

    moment = captured_at or datetime.now(UTC)
    snapshot: Snapshot = {
        "version": SNAPSHOT_VERSION,
        "kind": kind or _detect_kind(report),
        "target": str(report.get("target", "")),
        "capturedAt": moment.isoformat().replace("+00:00", "Z"),
        "report": report,
    }

    stem = f"{moment.strftime(_FILENAME_STAMP)}-{_slugify_target(snapshot['target'])}"
    path = directory / f"{stem}.json"
    # Two scans inside the same second would otherwise silently overwrite
    # each other, which is exactly the history a diff needs.
    suffix = 1
    while path.exists():
        path = directory / f"{stem}-{suffix}.json"
        suffix += 1

    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    if max_snapshots is not None:
        prune_snapshots(project_root, keep=max_snapshots)

    return path


def _read_ref(path: Path) -> SnapshotRef | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Skipping unreadable network snapshot %s: %s", path, exc)
        return None
    if not isinstance(raw, dict) or raw.get("version") != SNAPSHOT_VERSION:
        logger.warning("Skipping network snapshot %s: unsupported format", path)
        return None
    return {
        "path": str(path),
        "kind": str(raw.get("kind", "netscan")),
        "target": str(raw.get("target", "")),
        "capturedAt": str(raw.get("capturedAt", "")),
    }


def list_snapshots(project_root: str | Path) -> list[SnapshotRef]:
    """All readable snapshots for `project_root`, newest first.

    Unreadable or foreign-versioned files are skipped with a warning rather
    than raising — a corrupt file shouldn't break `archmap network diff`.
    """
    directory = snapshot_dir(project_root)
    if not directory.is_dir():
        return []

    refs = [ref for path in sorted(directory.glob("*.json")) if (ref := _read_ref(path))]
    refs.sort(key=lambda ref: (ref["capturedAt"], ref["path"]), reverse=True)
    return refs


def load_snapshot(path: str | Path) -> Snapshot:
    """Load a single snapshot file.

    Raises `ValueError` if the file isn't a snapshot this version understands.
    """
    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"{file_path} is not an ArchMAP network snapshot (v{SNAPSHOT_VERSION})")
    report = raw.get("report")
    if not isinstance(report, dict):
        raise ValueError(f"{file_path} has no scan report")
    return {
        "version": SNAPSHOT_VERSION,
        "kind": str(raw.get("kind", "netscan")),
        "target": str(raw.get("target", "")),
        "capturedAt": str(raw.get("capturedAt", "")),
        "report": report,
    }


def resolve_snapshot(project_root: str | Path, ref: str) -> Snapshot:
    """Resolve a user-facing snapshot reference into a loaded snapshot.

    Accepts `"latest"`, `"previous"`, a zero-based age index (`"0"` is the
    newest, `"1"` the one before it), or a path to a snapshot file.
    """
    candidate = Path(ref)
    if candidate.is_file():
        return load_snapshot(candidate)

    refs = list_snapshots(project_root)
    if not refs:
        raise ValueError(
            f"No network snapshots found in {snapshot_dir(project_root)}. "
            "Run `archmap expose <target> --snapshot` first."
        )

    key = ref.strip().lower()
    if key == "latest":
        index = 0
    elif key == "previous":
        index = 1
    elif key.isdigit():
        index = int(key)
    else:
        raise ValueError(
            f"Unknown snapshot reference '{ref}' — expected 'latest', 'previous', "
            "an age index like '2', or a path to a snapshot file."
        )

    if index >= len(refs):
        raise ValueError(
            f"Snapshot '{ref}' is out of range — only {len(refs)} snapshot(s) stored."
        )
    return load_snapshot(refs[index]["path"])


def latest_snapshot(project_root: str | Path) -> Snapshot | None:
    """The most recent snapshot, or `None` when the project has none.

    Used by `archmap memory`, which folds network observations into its
    digest when they exist and stays silent about them when they don't.
    """
    refs = list_snapshots(project_root)
    if not refs:
        return None
    try:
        return load_snapshot(refs[0]["path"])
    except (OSError, ValueError) as exc:
        logger.warning("Could not load latest network snapshot: %s", exc)
        return None


def prune_snapshots(project_root: str | Path, *, keep: int = DEFAULT_MAX_SNAPSHOTS) -> list[Path]:
    """Delete all but the `keep` newest snapshots; returns what was removed."""
    if keep < 0:
        raise ValueError("keep must be >= 0")

    removed: list[Path] = []
    for ref in list_snapshots(project_root)[keep:]:
        path = Path(ref["path"])
        try:
            path.unlink()
            removed.append(path)
        except OSError as exc:
            logger.warning("Could not prune network snapshot %s: %s", path, exc)
    return removed
