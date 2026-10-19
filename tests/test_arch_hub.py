from __future__ import annotations

import json
from pathlib import Path

from archmap.cli.arch_hub import ArchHubConfig, ArchHubRegistrar


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
