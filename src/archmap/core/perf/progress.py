"""Progress line with an ETA, written to a stream (stderr) and nowhere else."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TextIO

from archmap.core.perf.estimate import STAGE_SHARES

MIN_INTERVAL_SECONDS = 0.5
# A run is only worth a progress line when it is expected to take longer.
MIN_EXPECTED_SECONDS = 5.0
# Stages that run after parsing, in ``analyze_graph`` order (``STAGE_SHARES`` keys).
LATER_STAGES = ("cycles", "impact", "risk", "testMapping", "centrality", "findings")


def format_eta(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"~{max(1, round(seconds))} s left"
    return f"~{round(seconds / 60)} min left"


def _share_from(stage: str | None) -> float:
    """Share of the total run taken by ``stage`` and every later stage (``None`` = all later)."""
    start = LATER_STAGES.index(stage) if stage in LATER_STAGES else 0
    return sum(STAGE_SHARES[s] for s in LATER_STAGES[start:])


class Progress:
    """``\r[archmap] parse 4,210/12,345 · ~25 s left``, at most every 0.5 s.

    ``estimate_seconds`` is the predicted total run time. While parsing, the
    ETA is the measured parse rate extrapolated over the files left plus the
    estimate's share for the stages after parsing; each later stage shows its
    label with the estimate's share for itself and the stages after it, so the
    ETA keeps going down until the run ends. Writing never raises: a closed
    stream only silences the line.
    """

    def __init__(
        self,
        stream: TextIO,
        estimate_seconds: float,
        clock: Callable[[], float] = time.monotonic,
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
        return float(self._clock())

    def _write(self, text: str) -> bool:
        try:
            self._stream.write(text)
            self._stream.flush()
        except (OSError, ValueError):
            # A closed or broken stderr must never abort the analysis.
            return False
        return True

    def _emit(self, text: str, *, force: bool = False) -> None:
        now = self._now()
        if not force and now - self._last_emit < MIN_INTERVAL_SECONDS:
            return
        self._last_emit = now
        line = f"[archmap] {text}"
        pad = " " * max(0, self._width - len(line))
        if self._write(f"\r{line}{pad}"):
            self._width = len(line)
            self._dirty = True

    def _later_seconds(self, stage: str | None = None) -> float:
        return self._estimate * _share_from(stage)

    def stage(self, name: str) -> None:
        with self._lock:
            self._stage = name
            self._stage_started = self._now()
            if name == "analyze":
                text = f"{name} · {format_eta(self._later_seconds())}"
            elif name in LATER_STAGES:
                text = f"{name} · {format_eta(self._later_seconds(name))}"
            else:
                text = name
            self._emit(text, force=True)

    def advance(self, done: int, total: int) -> None:
        with self._lock:
            if total <= 0:
                return
            now = self._now()
            stage_elapsed = now - self._stage_started
            if done > 0 and stage_elapsed > 0:
                remaining = stage_elapsed / done * max(0, total - done)
            else:
                remaining = self._estimate * STAGE_SHARES["parse"] * (1 - done / total)
            remaining += self._later_seconds()
            self._emit(
                f"{self._stage} {done:,}/{total:,} · {format_eta(remaining)}",
                force=done >= total,
            )

    def close(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            self._write("\r" + " " * self._width + "\r")
            self._dirty = False
