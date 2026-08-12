from __future__ import annotations

import json
from argparse import Namespace

from archmap.cli import commands as cli_commands


def _base_args(**overrides) -> Namespace:
    defaults = dict(
        target="10.0.0.1",
        path=".",
        ports=None,
        top_ports=None,
        discover_only=False,
        no_discover=False,
        fingerprint=True,
        use_nmap=False,
        nmap_args=None,
        os_detection=False,
        scripts=False,
        timeout=1.0,
        concurrency=200,
        json=False,
        out=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


_SCAN_RESULT = {"target": "10.0.0.1", "hosts": []}
_ANALYSIS_RESULT = {"projectRoot": "/app", "nodes": []}
_CORRELATE_RESULT = {
    "target": "10.0.0.1",
    "projectRoot": "/app",
    "findings": [
        {
            "host": "10.0.0.1",
            "hostname": None,
            "port": 6379,
            "protocol": "tcp",
            "service": "redis",
            "networkRisk": {"level": "high", "reason": "Redis often runs unauthenticated"},
            "matchedPackages": [
                {"package": "redis", "nodeId": "pkg:redis", "impactCount": 3, "risk": "ok"}
            ],
            "severity": "high",
        }
    ],
    "summary": {"openPorts": 1, "matchedToCode": 1, "highSeverity": 1},
}


def _patch_pipeline(monkeypatch, correlate_result=_CORRELATE_RESULT) -> None:
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: _SCAN_RESULT)
    monkeypatch.setattr(cli_commands, "analyze_project", lambda path, **kwargs: _ANALYSIS_RESULT)
    monkeypatch.setattr(
        cli_commands, "correlate_exposure", lambda scan, analysis: correlate_result
    )


def test_run_expose_prints_human_report(monkeypatch, capsys) -> None:
    _patch_pipeline(monkeypatch)

    exit_code = cli_commands.run_expose(_base_args())

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Exposure Report" in out
    assert "redis" in out
    assert "HIGH" in out
    assert "pkg:redis" in out


def test_run_expose_json_output(monkeypatch, capsys) -> None:
    _patch_pipeline(monkeypatch)

    exit_code = cli_commands.run_expose(_base_args(json=True))

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed == _CORRELATE_RESULT


def test_run_expose_writes_out_file(monkeypatch, tmp_path) -> None:
    _patch_pipeline(monkeypatch)
    out_path = tmp_path / "expose.json"

    exit_code = cli_commands.run_expose(_base_args(json=True, out=str(out_path)))

    assert exit_code == 0
    assert json.loads(out_path.read_text()) == _CORRELATE_RESULT


def test_run_expose_handles_netscan_errors(monkeypatch, capsys) -> None:
    def _raise(*_a, **_k):
        raise RuntimeError("nmap not found")

    monkeypatch.setattr(cli_commands, "_scan_network", _raise)

    exit_code = cli_commands.run_expose(_base_args())

    assert exit_code == 1
    assert "nmap not found" in capsys.readouterr().err


def test_run_expose_handles_analyze_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_commands, "_scan_network", lambda target, **kwargs: _SCAN_RESULT)

    def _raise(*_a, **_k):
        raise FileNotFoundError("project path does not exist: /nope")

    monkeypatch.setattr(cli_commands, "analyze_project", _raise)

    exit_code = cli_commands.run_expose(_base_args())

    assert exit_code == 1
    assert "does not exist" in capsys.readouterr().err


def test_run_expose_no_findings(monkeypatch, capsys) -> None:
    empty_result = {
        "target": "10.0.0.1",
        "projectRoot": "/app",
        "findings": [],
        "summary": {"openPorts": 0, "matchedToCode": 0, "highSeverity": 0},
    }
    _patch_pipeline(monkeypatch, correlate_result=empty_result)

    exit_code = cli_commands.run_expose(_base_args())

    assert exit_code == 0
    assert "No open ports found." in capsys.readouterr().out
