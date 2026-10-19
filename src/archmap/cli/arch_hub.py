"""Optional registration of ``archmap serve`` in the Arch Hub (System-Arch).

The Arch Hub is the shared catalog of the Arch line (System-PVD, SIMPLE-ArCh,
ArchMAP, ...). The contract lives in ``System-Arch/docs/ARCH-LINE.md``; the
environment variables are the same in every system of the line:

``ARCHHUB_URL``                Hub base URL. Unset = integration disabled.
``ARCHHUB_TOKEN``              Sent as ``X-Hub-Token`` when the Hub requires it.
``ARCHHUB_PUBLIC_URL``         Address the Hub uses to reach this server.
``ARCHHUB_HEARTBEAT_SECONDS``  Heartbeat period (default 20, 0 = register only).

A Hub that is down never affects ``serve``: failures are printed once and retried.
Standard library only, like the rest of ArchMAP.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from archmap import __version__

SYSTEM_ID = "archmap"
DEFAULT_HEARTBEAT_SECONDS = 20
REQUEST_TIMEOUT_SECONDS = 5

# (url, body, headers) -> HTTP status. Injected in tests.
Poster = Callable[[str, bytes | None, dict[str, str]], int]


@dataclass(frozen=True)
class ArchHubConfig:
    hub_url: str
    token: str | None
    public_url: str
    heartbeat_seconds: int

    @classmethod
    def from_env(
        cls, public_url_fallback: str, env: Mapping[str, str] | None = None
    ) -> ArchHubConfig | None:
        env = os.environ if env is None else env
        hub_url = env.get("ARCHHUB_URL", "").strip().rstrip("/")
        if not hub_url:
            return None
        try:
            heartbeat = max(0, int(env.get("ARCHHUB_HEARTBEAT_SECONDS", "")))
        except ValueError:
            heartbeat = DEFAULT_HEARTBEAT_SECONDS
        public_url = env.get("ARCHHUB_PUBLIC_URL", "").strip() or public_url_fallback
        return cls(
            hub_url=hub_url,
            token=env.get("ARCHHUB_TOKEN") or None,
            public_url=public_url.rstrip("/"),
            heartbeat_seconds=heartbeat,
        )


def _urllib_post(url: str, body: bytes | None, headers: dict[str, str]) -> int:
    request = Request(url, data=body or b"", headers=headers, method="POST")
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status)
    except HTTPError as exc:
        return int(exc.code)


class ArchHubRegistrar:
    """Registers once, then heartbeats; re-registers if the Hub forgot us (404)."""

    def __init__(
        self,
        config: ArchHubConfig,
        project_path: Path,
        post: Poster = _urllib_post,
        log: Callable[[str], None] = print,
    ) -> None:
        self.config = config
        self.project_path = project_path
        self._post = post
        self._log = log
        self._registered = False
        self._warned = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _headers(self, json_body: bool) -> dict[str, str]:
        headers = {"Content-Type": "application/json"} if json_body else {}
        if self.config.token:
            headers["X-Hub-Token"] = self.config.token
        return headers

    def payload(self) -> dict[str, object]:
        base = self.config.public_url
        return {
            "id": SYSTEM_ID,
            "name": "ArchMAP",
            "baseUrl": base,
            "healthCheckUrl": f"{base}/api/health",
            "description": (
                f"Análise estática de arquitetura v{__version__} — "
                f"analisando '{self.project_path.name}'"
            ),
            "tags": ["arch-line", "role:insight", "python", "static-analysis"],
            "connectsTo": ["arch-hub"],
        }

    def tick(self) -> None:
        """One register-or-heartbeat step. Never raises."""
        hub = self.config.hub_url
        try:
            if self._registered:
                status = self._post(
                    f"{hub}/api/v1/systems/{SYSTEM_ID}/heartbeat", None, self._headers(False)
                )
                self._registered = status != 404
            else:
                body = json.dumps(self.payload()).encode("utf-8")
                status = self._post(f"{hub}/api/v1/systems", body, self._headers(True))
                self._registered = 200 <= status < 300
                if self._registered:
                    self._log(f"[info] Registered in Arch Hub {hub} as '{SYSTEM_ID}'")
                    self._warned = False
                elif not self._warned:
                    self._log(f"[warn] Arch Hub rejected registration: HTTP {status}")
                    self._warned = True
        except (URLError, OSError, ValueError) as exc:
            self._registered = False
            if not self._warned:
                self._log(f"[warn] Arch Hub unreachable at {hub}: {exc}")
                self._warned = True

    def _run(self) -> None:
        retry = 2.0
        while not self._stop.is_set():
            self.tick()
            if self._registered and self.config.heartbeat_seconds == 0:
                return
            if self._registered:
                delay, retry = float(self.config.heartbeat_seconds), 2.0
            else:
                delay = retry
                retry = min(retry * 2, max(float(self.config.heartbeat_seconds), 2.0))
            self._stop.wait(delay)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="arch-hub", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def start_arch_hub_registration(
    project_path: Path, public_url_fallback: str
) -> ArchHubRegistrar | None:
    """Starts the background registrar when ``ARCHHUB_URL`` is set; otherwise no-op."""
    config = ArchHubConfig.from_env(public_url_fallback)
    if config is None:
        return None
    registrar = ArchHubRegistrar(config, project_path)
    registrar.start()
    return registrar
