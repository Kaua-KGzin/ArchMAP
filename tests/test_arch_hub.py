from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from archmap.cli.arch_hub import (
    ArchHubConfig,
    ArchHubRegistrar,
    build_architecture_payload,
    resolve_system_id,
    run_hub_report,
)


def _config(**overrides: object) -> ArchHubConfig:
    values: dict[str, object] = {
        "hub_url": "http://hub:8080",
        "token": "s3cret",
        "public_url": "http://127.0.0.1:3000",
        "heartbeat_seconds": 0,
    }
    values.update(overrides)
    return ArchHubConfig(**values)  # type: ignore[arg-type]


class FakeHub:
    def __init__(self, *statuses: int) -> None:
        self.statuses = list(statuses)
        self.calls: list[tuple[str, bytes | None, dict[str, str]]] = []

    def __call__(self, url: str, body: bytes | None, headers: dict[str, str]) -> int:
        self.calls.append((url, body, headers))
        return self.statuses.pop(0)


def test_config_is_disabled_without_hub_url() -> None:
    assert ArchHubConfig.from_env("http://127.0.0.1:3000", env={}) is None


def test_config_reads_line_variables() -> None:
    config = ArchHubConfig.from_env(
        "http://127.0.0.1:3000",
        env={
            "ARCHHUB_URL": "http://hub:8080/",
            "ARCHHUB_PUBLIC_URL": "http://10.0.0.5:3100/",
            "ARCHHUB_HEARTBEAT_SECONDS": "bogus",
        },
    )
    assert config == ArchHubConfig("http://hub:8080", None, "http://10.0.0.5:3100", 20)


def test_registers_then_heartbeats_and_reregisters_after_hub_restart(tmp_path: Path) -> None:
    hub = FakeHub(201, 404, 200)
    registrar = ArchHubRegistrar(_config(), tmp_path, post=hub, log=lambda _: None)

    registrar.tick()
    registrar.tick()
    registrar.tick()

    assert [url for url, _, _ in hub.calls] == [
        "http://hub:8080/api/v1/systems",
        "http://hub:8080/api/v1/systems/archmap/heartbeat",
        "http://hub:8080/api/v1/systems",
    ]
    _, body, headers = hub.calls[0]
    assert headers["X-Hub-Token"] == "s3cret"
    payload = json.loads(body or b"{}")
    assert payload["id"] == "archmap"
    assert payload["healthCheckUrl"] == "http://127.0.0.1:3000/api/health"
    assert "arch-line" in payload["tags"]


def test_unreachable_hub_never_raises_and_warns_once(tmp_path: Path) -> None:
    def refuse(url: str, body: bytes | None, headers: dict[str, str]) -> int:
        raise OSError("connection refused")

    logs: list[str] = []
    registrar = ArchHubRegistrar(_config(), tmp_path, post=refuse, log=logs.append)
    registrar.tick()
    registrar.tick()

    assert len(logs) == 1
    assert "unreachable" in logs[0]


def _refuse(url: str, body: bytes | None, headers: dict[str, str]) -> int:
    raise OSError("connection refused")


class RecordingStop:
    """Stands in for the registrar's stop Event, recording each wait() delay."""

    def __init__(self, stop_after: int) -> None:
        self.delays: list[float] = []
        self._stop_after = stop_after

    def is_set(self) -> bool:
        return len(self.delays) >= self._stop_after

    def wait(self, delay: float) -> bool:
        self.delays.append(delay)
        return False

    def set(self) -> None:
        self._stop_after = 0


def _run_collecting_delays(registrar: ArchHubRegistrar, rounds: int) -> list[float]:
    stop = RecordingStop(rounds)
    registrar._stop = stop  # type: ignore[assignment]
    registrar._run()
    return stop.delays


def test_backoff_grows_up_to_the_heartbeat_period_when_hub_is_down(tmp_path: Path) -> None:
    registrar = ArchHubRegistrar(
        _config(heartbeat_seconds=20), tmp_path, post=_refuse, log=lambda _: None
    )
    assert _run_collecting_delays(registrar, 5) == [2.0, 4.0, 8.0, 16.0, 20.0]


def test_register_only_mode_still_backs_off_instead_of_hammering_the_hub(tmp_path: Path) -> None:
    """``ARCHHUB_HEARTBEAT_SECONDS=0`` means "register once", not "retry every 2s forever"."""
    registrar = ArchHubRegistrar(
        _config(heartbeat_seconds=0), tmp_path, post=_refuse, log=lambda _: None
    )
    delays = _run_collecting_delays(registrar, 5)

    assert delays == [2.0, 4.0, 8.0, 16.0, 32.0]
    assert delays == sorted(delays), "a down Hub must never be polled at a fixed short interval"


def test_heartbeat_rejection_warns_and_falls_back_to_registration(tmp_path: Path) -> None:
    """A rotated or mis-scoped token answers 403 forever unless we re-register."""
    hub = FakeHub(201, 403, 201)
    logs: list[str] = []
    registrar = ArchHubRegistrar(_config(), tmp_path, post=hub, log=logs.append)

    registrar.tick()  # register
    registrar.tick()  # heartbeat -> 403
    registrar.tick()  # must go back to registration, not heartbeat again

    assert [url for url, _, _ in hub.calls] == [
        "http://hub:8080/api/v1/systems",
        "http://hub:8080/api/v1/systems/archmap/heartbeat",
        "http://hub:8080/api/v1/systems",
    ]
    assert any("403" in message for message in logs)


# --------------------------------------------------------------------------- hub-report


def _project(tmp_path: Path, manifest_id: str | None = "demo-system") -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_text("X = 1\n", encoding="utf-8")
    if manifest_id:
        (tmp_path / "arch.json").write_text(json.dumps({"id": manifest_id}), encoding="utf-8")
    return tmp_path


def _args(path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "path": str(path),
        "system_id": None,
        "hub": "http://hub:8080",
        "token": "tok",
        "commit": "abc123",
        "ref": "main",
        "report_url": None,
        "dry_run": False,
        "strict": False,
        "json": False,
        "parallel": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resolve_system_id_prefers_flag_then_manifest_then_dirname(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert resolve_system_id(project, "explicit") == "explicit"
    assert resolve_system_id(project) == "demo-system"
    (project / "arch.json").unlink()
    assert resolve_system_id(project) == resolve_system_id(project)  # deterministic slug
    assert all(ch.islower() or ch.isdigit() or ch == "-" for ch in resolve_system_id(project))


def test_hub_report_posts_payload_to_system_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    hub = FakeHub(201)

    assert run_hub_report(_args(_project(tmp_path)), post=hub) == 0

    url, body, headers = hub.calls[0]
    assert url == "http://hub:8080/api/v1/systems/demo-system/architecture"
    assert headers["X-Hub-Token"] == "tok"
    payload = json.loads(body or b"{}")
    assert 0 <= payload["score"] <= 100
    assert payload["files"] >= 3
    assert payload["commit"] == "abc123"
    assert "published to http://hub:8080" in summary.read_text(encoding="utf-8")


def test_hub_report_without_hub_only_prints_unless_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARCHHUB_URL", raising=False)
    project = _project(tmp_path)
    hub = FakeHub()

    assert run_hub_report(_args(project, hub=None), post=hub) == 0
    assert run_hub_report(_args(project, hub=None, strict=True), post=hub) == 1
    assert hub.calls == []


def test_hub_report_rejection_fails_only_when_strict(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert run_hub_report(_args(project), post=FakeHub(403)) == 0
    assert run_hub_report(_args(project, strict=True), post=FakeHub(403)) == 1


def test_build_payload_tolerates_sparse_report() -> None:
    payload = build_architecture_payload({}, commit=None, ref=None, report_url=None)
    assert payload["score"] == 0
    assert payload["findings"] == 0
    assert payload["commit"] is None


def test_build_payload_tolerates_present_but_unusable_values() -> None:
    """Missing keys were handled; keys present with null/garbage crashed hub-report."""
    report = {
        "architecture": {"health": {"score": None, "grade": None}},
        "metrics": {
            "filesAnalyzed": None,
            "circularDependencyCount": "many",
            "architectureHealthScore": None,
        },
        "findings": "not-a-list",
    }
    payload = build_architecture_payload(report, commit=None, ref=None, report_url=None)

    assert payload["score"] == 0
    assert payload["files"] == 0
    assert payload["cycles"] == 0
    assert payload["findings"] == 0
    assert payload["grade"] is None


def test_hub_report_is_a_cli_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from archmap.cli.main import main

    assert (
        main(["hub-report", str(_project(tmp_path)), "--dry-run", "--json", "--no-parallel"]) == 0
    )
    out = capsys.readouterr().out
    assert '"systemId": "demo-system"' in out


def test_hub_report_json_stdout_stays_parseable_after_publishing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_hub_report(_args(_project(tmp_path), json=True), post=FakeHub(201)) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["systemId"] == "demo-system"
    assert "Published" in captured.err
