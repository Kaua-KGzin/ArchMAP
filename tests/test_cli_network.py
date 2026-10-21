from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from archmap.cli.commands import run_memory, run_network
from archmap.core.exposure.snapshots import save_snapshot


def _netscan_report(ports: list[int], target: str = "192.168.1.10") -> dict:
    return {
        "target": target,
        "engine": "python",
        "hosts": [
            {
                "ip": "192.168.1.10",
                "hostname": "db.local",
                "openPorts": [
                    {"port": port, "protocol": "tcp", "service": "unknown", "risk": None}
                    for port in ports
                ],
            }
        ],
    }


def _seed(root: Path, ports: list[int], *, day: int) -> None:
    save_snapshot(
        root, _netscan_report(ports), captured_at=datetime(2026, 8, day, 12, 0, tzinfo=UTC)
    )


def _diff_args(path: Path, **overrides) -> argparse.Namespace:
    defaults = dict(
        network_command="diff",
        path=str(path),
        snapshot_from="previous",
        snapshot_to="latest",
        json=False,
        out=None,
        fail_on_new_ports=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _list_args(path: Path, **overrides) -> argparse.Namespace:
    defaults = dict(network_command="list", path=str(path), json=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_network_without_a_subcommand_explains_itself(capsys) -> None:
    rc = run_network(argparse.Namespace(network_command=None))

    assert rc == 1
    assert "archmap network diff" in capsys.readouterr().err


def test_network_list_reports_an_empty_store(tmp_path: Path, capsys) -> None:
    rc = run_network(_list_args(tmp_path))

    assert rc == 0
    out = capsys.readouterr().out
    assert "No network snapshots" in out
    assert "--snapshot" in out


def test_network_list_shows_snapshots_newest_first(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22, 6379], day=13)

    rc = run_network(_list_args(tmp_path))

    assert rc == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if "2026-08-" in line]
    assert lines[0].strip().startswith("0   2026-08-13")
    assert lines[1].strip().startswith("1   2026-08-01")


def test_network_list_json(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)

    rc = run_network(_list_args(tmp_path, json=True))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["kind"] == "netscan"
    assert payload[0]["target"] == "192.168.1.10"


def test_network_diff_prints_what_changed(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22, 6379], day=13)

    rc = run_network(_diff_args(tmp_path))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Network Diff" in out
    assert "Ports opened (1)" in out
    assert "6379/tcp" in out


def test_network_diff_reports_no_change(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22], day=13)

    rc = run_network(_diff_args(tmp_path))

    assert rc == 0
    assert "No network changes" in capsys.readouterr().out


def test_network_diff_json_and_out_file(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22, 6379], day=13)
    out_file = tmp_path / "reports" / "network-diff.json"

    rc = run_network(_diff_args(tmp_path, json=True, out=str(out_file)))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["portsOpened"] == 1
    assert json.loads(out_file.read_text(encoding="utf-8")) == payload


def test_network_diff_fail_on_new_ports_gate(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22, 6379], day=13)

    rc = run_network(_diff_args(tmp_path, fail_on_new_ports=True))

    assert rc == 1
    assert "1 new open port(s)" in capsys.readouterr().err


def test_network_diff_gate_passes_when_nothing_opened(tmp_path: Path) -> None:
    _seed(tmp_path, [22, 6379], day=1)
    _seed(tmp_path, [22], day=13)

    assert run_network(_diff_args(tmp_path, fail_on_new_ports=True)) == 0


def test_network_diff_without_snapshots_errors_helpfully(tmp_path: Path, capsys) -> None:
    rc = run_network(_diff_args(tmp_path))

    assert rc == 1
    assert "No network snapshots found" in capsys.readouterr().err


def test_network_diff_with_a_single_snapshot_errors(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)

    rc = run_network(_diff_args(tmp_path))

    assert rc == 1
    assert "out of range" in capsys.readouterr().err


def test_network_diff_accepts_explicit_refs(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, [22], day=1)
    _seed(tmp_path, [22, 80], day=7)
    _seed(tmp_path, [22, 80, 6379], day=13)

    rc = run_network(_diff_args(tmp_path, snapshot_from="2", snapshot_to="latest"))

    assert rc == 0
    assert "Ports opened (2)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# `archmap memory` picking up the stored snapshot
# ---------------------------------------------------------------------------


def _memory_args(path: Path, **overrides) -> argparse.Namespace:
    defaults = dict(
        path=str(path),
        out=None,
        print_only=True,
        quiet=False,
        parallel=True,
        network=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _write_small_project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("import os\n", encoding="utf-8")


def test_memory_folds_in_the_latest_snapshot(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)
    save_snapshot(
        tmp_path,
        {
            "target": "192.168.1.10",
            "findings": [
                {
                    "host": "192.168.1.10",
                    "hostname": None,
                    "port": 6379,
                    "protocol": "tcp",
                    "service": "redis",
                    "networkRisk": {"level": "high", "reason": "no auth"},
                    "severity": "high",
                    "confidence": 0.95,
                    "driftViolation": None,
                }
            ],
            "driftViolations": [],
        },
    )

    rc = run_memory(_memory_args(tmp_path))

    assert rc == 0
    out = capsys.readouterr().out
    assert "## Network exposure" in out
    assert "192.168.1.10:6379" in out


def test_memory_no_network_flag_skips_the_section(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)
    _seed(tmp_path, [6379], day=13)

    rc = run_memory(_memory_args(tmp_path, network=False))

    assert rc == 0
    assert "## Network exposure" not in capsys.readouterr().out


def test_memory_is_unaffected_when_no_snapshot_exists(tmp_path: Path, capsys) -> None:
    _write_small_project(tmp_path)

    rc = run_memory(_memory_args(tmp_path))

    assert rc == 0
    assert "## Network exposure" not in capsys.readouterr().out
