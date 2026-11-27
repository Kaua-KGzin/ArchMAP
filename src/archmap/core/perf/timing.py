from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager


class StageTimer:
    """Accumulates wall-clock time per named stage, in milliseconds."""

    def __init__(self) -> None:
        self._ms: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self._ms[name] = self._ms.get(name, 0.0) + elapsed

    def as_dict(self) -> dict[str, float]:
        return {name: round(ms, 1) for name, ms in self._ms.items()}
