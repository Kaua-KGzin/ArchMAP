from __future__ import annotations

import importlib.resources
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from archmap.core import analyze_project
from archmap.core.advisor import advise_architecture
from archmap.utils.file_utils import normalize_file_id


@dataclass
class ReportState:
    path: Path
    report: dict
    history_cache: dict[tuple[str, int], dict] = field(default_factory=dict)
    _listeners: list[threading.Event] = field(default_factory=list, repr=False)
    _listeners_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_path(cls, path: str | Path, **_kwargs) -> ReportState:
        resolved = Path(path).resolve()
        return cls(
            path=resolved,
            report=analyze_project(resolved),
        )

    def set_path(self, new_path: Path) -> None:
        self.path = new_path.resolve()
        self.reanalyze()

    def reanalyze(self) -> None:
        self.report = analyze_project(self.path)
        self.history_cache.clear()
        self.notify_listeners()

    def notify_listeners(self) -> None:
        with self._listeners_lock:
            for event in self._listeners:
                event.set()

    def history(self, *, ref: str = "HEAD", limit: int = 12) -> dict:
        cache_key = (ref, limit)
        if cache_key not in self.history_cache:
            self.history_cache[cache_key] = {"snapshots": [], "windowSize": 0, "ref": ref}
        return self.history_cache[cache_key]


def resolve_static_dir() -> Path:
    # PyInstaller frozen bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "web-ui" / "static"

    # Installed wheel: static files are bundled inside the archmap package
    try:
        pkg_ref = importlib.resources.files("archmap") / "web-ui" / "static"
        pkg_path = Path(str(pkg_ref))
        if pkg_path.is_dir():
            return pkg_path
    except (TypeError, AttributeError):
        pass

    # Source-checkout fallback: src/archmap/web-ui/static
    return Path(__file__).resolve().parents[1] / "web-ui" / "static"


_REANALYZE_COOLDOWN: float = 2.0


def build_http_handler(state: ReportState, static_dir: Path) -> type[SimpleHTTPRequestHandler]:
    health_payload = {"status": "ok"}
    _reanalyze_lock = threading.Lock()
    _reanalyze_last: list[float] = [0.0]

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def _is_local_request(self) -> bool:
            return self.client_address[0] in {"127.0.0.1", "::1", "localhost"}

        def do_POST(self):  # noqa: N802
            if self.path == "/api/advise":
                self._handle_advise()
                return
            if self.path == "/api/open":
                if not self._is_local_request():
                    self._write_json(
                        HTTPStatus.FORBIDDEN,
                        {"status": "error", "message": "only available on localhost"},
                    )
                    return
                self._handle_open_project()
                return
            if self.path == "/api/open-file":
                if not self._is_local_request():
                    self._write_json(
                        HTTPStatus.FORBIDDEN,
                        {"status": "error", "message": "only available on localhost"},
                    )
                    return
                self._handle_open_file()
                return
            if self.path == "/api/project":
                self._handle_set_project()
                return
            if self.path == "/api/reanalyze":
                self._handle_reanalyze()
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_GET(self):  # noqa: N802
            parsed_url = urlsplit(self.path)
            request_path = parsed_url.path

            if request_path == "/api/graph":
                self._write_json(HTTPStatus.OK, state.report)
                return

            if request_path == "/api/history":
                self._handle_history(parsed_url.query)
                return

            if request_path == "/api/project":
                self._write_json(HTTPStatus.OK, {"path": str(state.path)})
                return

            if request_path == "/api/health":
                self._write_json(HTTPStatus.OK, health_payload)
                return

            if request_path == "/api/badge":
                self._handle_badge()
                return

            if request_path == "/api/events":
                self._handle_events()
                return

            if request_path == "/":
                self.path = "/index.html"
            elif request_path != self.path:
                self.path = request_path

            super().do_GET()

        def _handle_open_project(self) -> None:
            new_path, picker_error = self._pick_directory()
            if picker_error:
                self._write_json(
                    HTTPStatus.NOT_IMPLEMENTED,
                    {
                        "status": "unsupported",
                        "mode": "manual_path",
                        "message": picker_error,
                    },
                )
                return

            if not new_path:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            try:
                state.set_path(new_path)
            except (OSError, RuntimeError, ValueError) as exc:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(
                HTTPStatus.OK,
                {"status": "success", "path": str(new_path.resolve())},
            )

        def _handle_set_project(self) -> None:
            payload = self._read_json_body()
            next_path = str(payload.get("path", "")).strip()
            if not next_path:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"status": "error", "message": "body.path is required"},
                )
                return

            resolved = Path(next_path).resolve()
            if not resolved.is_dir():
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"status": "error", "message": "path must be an existing directory"},
                )
                return

            try:
                state.set_path(resolved)
            except (OSError, RuntimeError, ValueError) as exc:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(
                HTTPStatus.OK,
                {"status": "success", "path": str(state.path)},
            )

        def _handle_open_file(self) -> None:
            payload = self._read_json_body()
            node_id = str(payload.get("nodeId", "")).strip()
            if not node_id:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"status": "error", "message": "body.nodeId is required"},
                )
                return

            target_path = _resolve_node_file_path(state.path, state.report, node_id)
            if target_path is None:
                self._write_json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "status": "error",
                        "message": f"File node not found or unavailable: {node_id}",
                    },
                )
                return

            try:
                _open_local_path(target_path)
            except (OSError, RuntimeError) as exc:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(
                HTTPStatus.OK,
                {"status": "success", "path": str(target_path)},
            )

        def _handle_reanalyze(self) -> None:
            now = time.monotonic()
            with _reanalyze_lock:
                elapsed = now - _reanalyze_last[0]
                if elapsed < _REANALYZE_COOLDOWN:
                    self._write_json(
                        HTTPStatus.TOO_MANY_REQUESTS,
                        {
                            "status": "error",
                            "message": (
                                f"rate limit: wait {_REANALYZE_COOLDOWN:.0f}s between requests"
                            ),
                        },
                    )
                    return
                _reanalyze_last[0] = now

            try:
                state.reanalyze()
            except (OSError, RuntimeError, ValueError) as exc:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(HTTPStatus.OK, {"status": "success", "path": str(state.path)})

        def _handle_history(self, query_string: str) -> None:
            query = parse_qs(query_string)
            ref = str(query.get("ref", ["HEAD"])[0] or "HEAD").strip() or "HEAD"
            limit = _parse_history_limit(query.get("limit", ["12"])[0])

            try:
                history = state.history(ref=ref, limit=limit)
            except (OSError, RuntimeError, ValueError) as exc:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"status": "error", "message": str(exc)},
                )
                return

            self._write_json(HTTPStatus.OK, history)

        def _handle_events(self) -> None:
            event = threading.Event()
            with state._listeners_lock:
                state._listeners.append(event)

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            try:
                # Initial connected message
                self.wfile.write(b"data: connected\n\n")
                self.wfile.flush()

                while True:
                    # Wait for 30s or until notified
                    if event.wait(timeout=30):
                        self.wfile.write(b"data: reload\n\n")
                        self.wfile.flush()
                        event.clear()
                    else:
                        # Keep-alive ping
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError, OSError):
                # Client disconnected
                pass
            finally:
                with state._listeners_lock:
                    if event in state._listeners:
                        state._listeners.remove(event)

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self';"
                " script-src 'self';"
                " style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;"
                " font-src 'self' https://fonts.gstatic.com;"
                " img-src 'self' data:;"
                " connect-src 'self'",
            )
            super().end_headers()

        def _write_json(self, status: HTTPStatus, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            _MAX_BODY_BYTES = 1_048_576  # 1 MB

            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except (ValueError, TypeError):
                return {}

            if content_length <= 0 or content_length > _MAX_BODY_BYTES:
                return {}

            body = self.rfile.read(content_length)
            if not body:
                return {}

            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}

            return payload if isinstance(payload, dict) else {}

        def _pick_directory(self) -> tuple[Path | None, str | None]:
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                try:
                    root.withdraw()
                    root.attributes("-topmost", True)
                    directory = filedialog.askdirectory(title="ArchMAP - Select Project Folder")
                    return (Path(directory), None) if directory else (None, None)
                finally:
                    root.destroy()
            except (ImportError, OSError, RuntimeError) as exc:
                return None, _describe_directory_picker_error(exc)

        def _handle_badge(self) -> None:
            health = state.report.get("architecture", {}).get("health", {})
            score = int(health.get("score", 100))
            grade = str(health.get("grade", "A"))
            svg = _build_badge_svg(score, grade)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg)))
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(svg)

        def _handle_advise(self) -> None:
            _VALID_PROVIDERS = {"claude", "openai", "ollama", "custom"}
            payload = self._read_json_body()
            provider = str(payload.get("provider", "ollama")).strip().lower()
            if provider not in _VALID_PROVIDERS:
                valid = ", ".join(sorted(_VALID_PROVIDERS))
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"status": "error", "message": f"provider must be one of: {valid}"},
                )
                return

            model = payload.get("model") or None
            base_url = payload.get("base_url") or None
            api_key = payload.get("api_key") or None
            try:
                timeout = int(payload.get("timeout") or 90)
            except (ValueError, TypeError):
                timeout = 90

            try:
                result = advise_architecture(
                    state.report,
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    timeout=timeout,
                )
            except RuntimeError as exc:
                self._write_json(
                    HTTPStatus.BAD_GATEWAY,
                    {"status": "error", "message": str(exc)},
                )
                return
            except (TimeoutError, OSError) as exc:
                self._write_json(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    {"status": "error", "message": f"LLM request timed out or connection failed: {exc}"},  # noqa: E501
                )
                return

            self._write_json(HTTPStatus.OK, {"status": "success", **result})

        def log_message(self, _format: str, *args) -> None:
            return

    return Handler


def _describe_directory_picker_error(exc: Exception) -> str:
    exc_name = exc.__class__.__name__
    message = str(exc).strip()
    fallback_message = (
        "Native folder picker unavailable in this environment. "
        "Enter the project path manually."
    )

    if exc_name in {"ImportError", "ModuleNotFoundError"}:
        return fallback_message
    if message:
        return f"Native folder picker unavailable: {message}. Enter the project path manually."
    return fallback_message


def _resolve_node_file_path(project_path: Path, report: dict, node_id: str) -> Path | None:
    nodes = report.get("nodes", [])
    node = next((entry for entry in nodes if entry.get("id") == node_id), None)
    if not node or node.get("type") != "file":
        return None

    normalized_node_id = normalize_file_id(node_id)
    project_root = Path(report.get("projectRoot", project_path)).resolve()
    candidate = _candidate_file_path(project_root, normalized_node_id)
    if candidate is None or not candidate.is_file():
        return None
    return candidate


def _candidate_file_path(project_root: Path, normalized_node_id: str) -> Path | None:
    relative_path = Path(normalized_node_id.replace("/", os.sep))
    resolved_root = project_root.resolve()

    if resolved_root.is_file():
        if normalize_file_id(resolved_root.name) == normalized_node_id:
            return resolved_root
        candidate = (resolved_root.parent / relative_path).resolve()
        try:
            candidate.relative_to(resolved_root.parent)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    candidate = (resolved_root / relative_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _open_local_path(target_path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(target_path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        try:
            subprocess.Popen(
                ["open", str(target_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
        return
    if _is_termux():
        try:
            subprocess.Popen(
                ["termux-open", str(target_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
        return
    try:
        subprocess.Popen(
            ["xdg-open", str(target_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def _is_termux() -> bool:
    if os.environ.get("TERMUX_VERSION"):
        return True
    prefix = os.environ.get("PREFIX", "")
    if prefix.startswith("/data/data/com.termux") or prefix.startswith("/data/user/"):
        return True
    return Path("/data/data/com.termux").exists()


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _parse_history_limit(raw_value: object) -> int:
    try:
        parsed = int(str(raw_value))
    except (TypeError, ValueError):
        return 12
    return max(1, min(50, parsed))


_BADGE_COLORS: dict[str, str] = {
    "A": "#4c1",
    "B": "#a3c51c",
    "C": "#dfb317",
    "D": "#fe7d37",
    "F": "#e05d44",
}


def _build_badge_svg(score: int, grade: str) -> bytes:
    color = _BADGE_COLORS.get(grade, "#9f9f9f")
    label = "ArchMAP"
    value = f"{score} {grade}"
    label_w = 62
    value_w = max(36, len(value) * 7 + 10)
    total_w = label_w + value_w
    label_cx = label_w // 2
    value_cx = label_w + value_w // 2
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20">'
        f'<rect width="{label_w}" height="20" fill="#555"/>'
        f'<rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>'
        f'<text x="{label_cx}" y="14" fill="#fff" font-size="11" text-anchor="middle"'
        f' font-family="DejaVu Sans,Verdana,Geneva,sans-serif">{label}</text>'
        f'<text x="{value_cx}" y="14" fill="#fff" font-size="11" text-anchor="middle"'
        f' font-family="DejaVu Sans,Verdana,Geneva,sans-serif">{value}</text>'
        f"</svg>"
    )
    return svg.encode("utf-8")


def can_open_browser(host: str) -> bool:
    if _is_termux():
        return False
    if sys.platform.startswith("linux") and not _has_display():
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::", "::1"}


def browser_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "localhost"
    return host
