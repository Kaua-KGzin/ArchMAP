from __future__ import annotations

import json
from argparse import Namespace

from archmap.cli import commands as cli_commands


def _base_args(**overrides) -> Namespace:
    defaults = dict(
        target="10.0.0.1",
        ports=None,
        top_ports=None,
        discover_only=False,
        no_discover=False,
        fingerprint=True,
        use_nmap=False,
        nmap_args=None,
        timeout=1.0,
        concurrency=200,
        json=False,
        out=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_run_netscan_prints_human_report(monkeypatch, capsys) -> None:
    report = {
        "target": "10.0.0.1",
        "engine": "python",
        "hostsScanned": 1,
        "discoverOnly": False,
        "durationSeconds": 0.01,
        "hosts": [
            {
                "ip": "10.0.0.1",
                "hostname": "box.local",
                "status": "up",
                "openPorts": [
                    {
                        "port": 22,
                        "protocol": "tcp",
                        "state": "open",
                        "service": "ssh",
                        "banner": None,
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: report)

    exit_code = cli_commands.run_netscan(_base_args())

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "10.0.0.1" in out
    assert "22/tcp" in out
    assert "ssh" in out


def test_run_netscan_json_output(monkeypatch, capsys) -> None:
    report = {"target": "10.0.0.1", "engine": "python", "hosts": [], "durationSeconds": 0.0}
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: report)

    exit_code = cli_commands.run_netscan(_base_args(json=True))

    assert exit_code == 0
    out = capsys.readouterr().out
    printed = json.loads(out.strip())
    assert printed == report


def test_run_netscan_writes_out_file(monkeypatch, tmp_path) -> None:
    report = {"target": "10.0.0.1", "engine": "python", "hosts": [], "durationSeconds": 0.0}
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: report)
    out_path = tmp_path / "scan.json"

    exit_code = cli_commands.run_netscan(_base_args(json=True, out=str(out_path)))

    assert exit_code == 0
    assert json.loads(out_path.read_text()) == report


def test_run_netscan_handles_errors(monkeypatch, capsys) -> None:
    def _raise(*_a, **_k):
        raise RuntimeError("nmap not found")

    monkeypatch.setattr(cli_commands, "_scan_network", _raise)

    exit_code = cli_commands.run_netscan(_base_args())

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "nmap not found" in err


def test_run_netscan_no_hosts_found(monkeypatch, capsys) -> None:
    report = {"target": "10.0.0.1", "engine": "python", "hosts": [], "durationSeconds": 0.0}
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: report)

    exit_code = cli_commands.run_netscan(_base_args())

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "No live hosts found." in out
