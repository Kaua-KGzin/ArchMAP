"""Soft time budget for one analysis run.

The budget covers the wall time of the whole run, measured from when the
``Budget`` is created. It is *soft*: it is checked before each reducible
stage and inside the loops that already iterate in steps, so a run can
overshoot. Parsing is never cut short, and some other stages never check it.

Reducible stages and how each is reduced:

- ``impact``: once the budget is used up, the remaining files get an empty
  ``impactedFiles`` list (``impactedFilesTruncated: true``); ``impactCount``
  and ``risk`` stay exact.
- ``centrality``: skipped when the budget is already used up; run on a
  ``CENTRALITY_REDUCED_SAMPLES``-file sample when its projected time does not
  fit what is left; stops early with what it has once the budget runs out.

Every reduction is recorded so the report, a ``QUAL-*`` finding and the CLI
can say what changed and how to lift the limit.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any, Literal, TypedDict, get_args

BudgetSource = Literal["cli", "config", "mcp-default", "mcp-arg", "api"]
CENTRALITY_REDUCED_SAMPLES = 64
HOW_TO_CHANGE = (
    "Change it with --time-budget (CLI) or the time_budget argument (MCP, API), "
    "[analysis.limits] time_budget_seconds, or 0 for no limit"
)


class Reduction(TypedDict):
    stage: str
    reason: str
    detail: str


class BudgetInfo(TypedDict):
    seconds: float
    source: str


def validate_budget_seconds(seconds: float | None) -> float | None:
    """``None`` / ``0`` -> ``None`` (no limit); negative or non-finite -> ``ValueError``."""
    if seconds is None:
        return None
    value = float(seconds)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"time budget must be >= 0 seconds (0 means no limit), got {seconds!r}")
    return value or None


class Budget:
    def __init__(
        self,
        seconds: float | None,
        *,
        source: BudgetSource,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if source not in get_args(BudgetSource):
            raise ValueError(f"unknown time budget source: {source!r}")
        self.seconds = validate_budget_seconds(seconds)
        self.source: BudgetSource = source
        self.reductions: list[Reduction] = []
        self._clock = clock
        self._started = clock()

    @property
    def active(self) -> bool:
        return self.seconds is not None

    def remaining(self) -> float | None:
        """Seconds left, never below 0; ``None`` when there is no limit."""
        if self.seconds is None:
            return None
        return max(0.0, self.seconds - (self._clock() - self._started))

    def exhausted(self) -> bool:
        remaining = self.remaining()
        return remaining is not None and remaining <= 0

    def allows(self, stage: str, expected_seconds: float) -> bool:
        """Whether ``stage``, expected to take ``expected_seconds``, fits what is left."""
        remaining = self.remaining()
        if remaining is None:
            return True
        return remaining > 0 and expected_seconds <= remaining

    def record(self, stage: str, reason: str, detail: str) -> None:
        self.reductions.append({"stage": stage, "reason": reason, "detail": detail})

    def describe(self) -> BudgetInfo | None:
        """``metrics.analysisQuality.budget``; ``None`` when there is no limit."""
        if self.seconds is None:
            return None
        return {"seconds": self.seconds, "source": self.source}

    def message(self, reduction: Reduction) -> str:
        info = self.describe()
        if info is None:
            raise ValueError("no time budget is active")
        return reduction_message(reduction, info)


def stamp_full_report(report: dict[str, Any], budget: Budget) -> dict[str, Any]:
    """Re-stamp a cached *full* report with the budget of the current call.

    Only unreduced reports are ever cached, so the stored report is valid for
    any budget; only ``metrics.analysisQuality.budget`` / ``reductions`` must
    say which budget this call ran under (both absent when there is none).
    """
    quality = report.get("metrics", {}).get("analysisQuality")
    if not isinstance(quality, dict):
        return report
    info = budget.describe()
    if info is None:
        quality.pop("budget", None)
        quality.pop("reductions", None)
    else:
        quality["budget"] = info
        quality["reductions"] = []
    return report


def reduction_message(reduction: Reduction, budget: BudgetInfo) -> str:
    """The text shared by the ``QUAL-*`` finding and the CLI ``[budget]`` line."""
    return (
        f"{reduction['stage']} was reduced by the {budget['seconds']:g} s time budget "
        f"({budget['source']}): {reduction['detail']}"
    )
