from __future__ import annotations

import importlib.util
import tracemalloc
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py"


def _load():
    spec = importlib.util.spec_from_file_location("archmap_benchmark", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_timing_passes_are_untraced_and_memory_pass_is_separate(monkeypatch):
    bench = _load()
    real = bench.analyze_project
    tracing: list[bool] = []

    def spy(*args, **kwargs):
        tracing.append(tracemalloc.is_tracing())
        return real(*args, **kwargs)

    monkeypatch.setattr(bench, "analyze_project", spy)
    row = bench.run_size(20, "python", "layered", repeat=2)
    assert tracing == [False, False, True]
    assert row["peakMb"] is not None and row["seconds"] > 0
    assert "impact" in row["stagesMs"]


def test_no_memory_skips_traced_pass(monkeypatch):
    bench = _load()
    real = bench.analyze_project
    tracing: list[bool] = []

    def spy(*args, **kwargs):
        tracing.append(tracemalloc.is_tracing())
        return real(*args, **kwargs)

    monkeypatch.setattr(bench, "analyze_project", spy)
    row = bench.run_size(20, "python", "layered", repeat=1, measure_memory=False)
    assert tracing == [False]
    assert row["peakMb"] is None
