from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class StageTimer:
    """Accumulates wall-clock time per named stage, in milliseconds.

    ``on_stage`` (optional) is called with the stage name as each stage starts;
    the CLI progress line uses it. It only observes, never changes timings.
    """

    def __init__(self, on_stage: Callable[[str], None] | None = None) -> None:
        self._ms: dict[str, float] = {}
        self._on_stage = on_stage

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        if self._on_stage is not None:
            self._on_stage(name)
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self._ms[name] = self._ms.get(name, 0.0) + elapsed

    def as_dict(self) -> dict[str, float]:
        return {name: round(ms, 1) for name, ms in self._ms.items()}
