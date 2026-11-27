"""Progress line with an ETA, written to a stream (stderr) and nowhere else."""

from __future__ import annotations

import threading
import time
from typing import TextIO

MIN_INTERVAL_SECONDS = 0.5
# A run is only worth a progress line when it is expected to take longer.
MIN_EXPECTED_SECONDS = 5.0


def format_eta(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"~{max(1, round(seconds))} s left"
    return f"~{round(seconds / 60)} min left"


class Progress:
    """``\r[archmap] parse 4,210/12,345 · ~25 s left``, at most every 0.5 s.

    ``estimate_seconds`` is the predicted total run time; it feeds the ETA
    until enough files are done to extrapolate from the measured rate.
    """

    def __init__(
        self,
        stream: TextIO,
        estimate_seconds: float,
        clock: object = time.monotonic,
    ) -> None:
        self._stream = stream
        self._estimate = max(0.0, estimate_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self._started = self._now()
        self._stage_started = self._started
        self._stage = ""
        self._last_emit = float("-inf")
        self._width = 0
        self._dirty = False

    def _now(self) -> float:
        return float(self._clock())  # type: ignore[operator]

    def _emit(self, text: str, *, force: bool = False) -> None:
        now = self._now()
        if not force and now - self._last_emit < MIN_INTERVAL_SECONDS:
            return
        self._last_emit = now
        line = f"[archmap] {text}"
        pad = " " * max(0, self._width - len(line))
        self._width = len(line)
        self._stream.write(f"\r{line}{pad}")
        self._stream.flush()
        self._dirty = True

    def stage(self, name: str) -> None:
        with self._lock:
            self._stage = name
            self._stage_started = self._now()
            self._emit(name, force=True)

    def advance(self, done: int, total: int) -> None:
        with self._lock:
            if total <= 0:
                return
            now = self._now()
            stage_elapsed = now - self._stage_started
            if done > 0 and stage_elapsed > 0:
                remaining = stage_elapsed / done * max(0, total - done)
            else:
                remaining = self._estimate * (1 - done / total)
            self._emit(
                f"{self._stage} {done:,}/{total:,} · {format_eta(remaining)}",
                force=done >= total,
            )

    def close(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            self._stream.write("\r" + " " * self._width + "\r")
            self._stream.flush()
            self._dirty = False
