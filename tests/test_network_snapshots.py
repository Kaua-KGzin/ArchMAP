from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from archmap.core.exposure.snapshots import (
    SNAPSHOT_VERSION,
    latest_snapshot,
    list_snapshots,
    load_snapshot,
    prune_snapshots,
    resolve_snapshot,
    save_snapshot,
    snapshot_dir,
)

_NETSCAN_REPORT = {
    "target": "192.168.1.0/24",
    "engine": "python",
    "hosts": [
        {
            "ip": "192.168.1.10",
            "hostname": "db.local",
            "openPorts": [{"port": 5432, "protocol": "tcp", "service": "postgresql"}],
        }
    ],
}

_EXPOSE_REPORT = {
    "target": "192.168.1.10",
    "projectRoot": "/app",
    "findings": [{"host": "192.168.1.10", "port": 6379, "protocol": "tcp", "service": "redis"}],
    "driftViolations": [],
}


def _save(tmp_path, report, *, day: int, **kwargs):
    return save_snapshot(
        tmp_path, report, captured_at=datetime(2026, 8, day, 12, 0, tzinfo=UTC), **kwargs
    )


def test_save_snapshot_writes_into_archmap_network(tmp_path):
    path = _save(tmp_path, _NETSCAN_REPORT, day=1)

    assert path.parent == snapshot_dir(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == SNAPSHOT_VERSION
    assert payload["kind"] == "netscan"
    assert payload["target"] == "192.168.1.0/24"
    assert payload["capturedAt"] == "2026-08-01T12:00:00Z"
    # The report is stored verbatim so a snapshot replays exactly what was seen.
    assert payload["report"] == _NETSCAN_REPORT


def test_save_snapshot_infers_expose_kind_from_findings(tmp_path):
    path = _save(tmp_path, _EXPOSE_REPORT, day=1)

    assert json.loads(path.read_text(encoding="utf-8"))["kind"] == "expose"


def test_save_snapshot_does_not_overwrite_a_same_second_scan(tmp_path):
    # Same target and same timestamp — the filename would collide.
    first = _save(tmp_path, _NETSCAN_REPORT, day=1)
    second = _save(tmp_path, _NETSCAN_REPORT, day=1)

    assert first != second
    assert second.stem.endswith("-1")
    assert len(list_snapshots(tmp_path)) == 2


def test_list_snapshots_is_newest_first(tmp_path):
    _save(tmp_path, _NETSCAN_REPORT, day=1)
    _save(tmp_path, _NETSCAN_REPORT, day=13)

    captured = [ref["capturedAt"] for ref in list_snapshots(tmp_path)]
    assert captured == ["2026-08-13T12:00:00Z", "2026-08-01T12:00:00Z"]


def test_list_snapshots_on_a_project_that_never_scanned(tmp_path):
    assert list_snapshots(tmp_path) == []


def test_list_snapshots_skips_corrupt_files(tmp_path):
    _save(tmp_path, _NETSCAN_REPORT, day=1)
    (snapshot_dir(tmp_path) / "broken.json").write_text("{not json", encoding="utf-8")
    (snapshot_dir(tmp_path) / "future.json").write_text(
        json.dumps({"version": 999, "report": {}}), encoding="utf-8"
    )

    assert len(list_snapshots(tmp_path)) == 1


def test_resolve_snapshot_by_keyword_and_index(tmp_path):
    _save(tmp_path, _NETSCAN_REPORT, day=1)
    _save(tmp_path, _EXPOSE_REPORT, day=13)

    assert resolve_snapshot(tmp_path, "latest")["kind"] == "expose"
    assert resolve_snapshot(tmp_path, "previous")["kind"] == "netscan"
    assert resolve_snapshot(tmp_path, "0")["kind"] == "expose"
    assert resolve_snapshot(tmp_path, "1")["kind"] == "netscan"


def test_resolve_snapshot_by_path(tmp_path):
    path = _save(tmp_path, _NETSCAN_REPORT, day=1)

    assert resolve_snapshot(tmp_path, str(path))["target"] == "192.168.1.0/24"


def test_resolve_snapshot_errors_point_at_the_fix(tmp_path):
    with pytest.raises(ValueError, match="--snapshot"):
        resolve_snapshot(tmp_path, "latest")

    _save(tmp_path, _NETSCAN_REPORT, day=1)
    with pytest.raises(ValueError, match="out of range"):
        resolve_snapshot(tmp_path, "5")
    with pytest.raises(ValueError, match="Unknown snapshot reference"):
        resolve_snapshot(tmp_path, "yesterday")


def test_load_snapshot_rejects_a_foreign_file(tmp_path):
    stray = tmp_path / "stray.json"
    stray.write_text(json.dumps({"hosts": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="not an ArchMAP network snapshot"):
        load_snapshot(stray)


def test_load_snapshot_rejects_a_snapshot_without_a_report(tmp_path):
    stray = tmp_path / "stray.json"
    stray.write_text(json.dumps({"version": SNAPSHOT_VERSION}), encoding="utf-8")

    with pytest.raises(ValueError, match="no scan report"):
        load_snapshot(stray)


def test_latest_snapshot_returns_none_without_history(tmp_path):
    assert latest_snapshot(tmp_path) is None


def test_latest_snapshot_returns_the_newest(tmp_path):
    _save(tmp_path, _NETSCAN_REPORT, day=1)
    _save(tmp_path, _EXPOSE_REPORT, day=13)

    snapshot = latest_snapshot(tmp_path)
    assert snapshot is not None
    assert snapshot["capturedAt"] == "2026-08-13T12:00:00Z"


def test_saving_prunes_the_oldest_snapshots(tmp_path):
    for day in range(1, 6):
        _save(tmp_path, _NETSCAN_REPORT, day=day, max_snapshots=3)

    captured = [ref["capturedAt"] for ref in list_snapshots(tmp_path)]
    assert captured == [
        "2026-08-05T12:00:00Z",
        "2026-08-04T12:00:00Z",
        "2026-08-03T12:00:00Z",
    ]


def test_prune_snapshots_rejects_a_negative_keep(tmp_path):
    with pytest.raises(ValueError, match="keep must be >= 0"):
        prune_snapshots(tmp_path, keep=-1)
