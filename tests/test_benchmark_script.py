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


def test_markdown_table_comes_from_the_baseline_file(tmp_path):
    import json

    bench = _load()
    payload = {
        "rows": [
            {"files": 1000, "language": "python", "shape": "cycle",
             "seconds": 1.234, "peakMb": 8.1},
            {"files": 5000, "language": "python", "shape": "cycle",
             "seconds": 3.0, "peakMb": None},
        ]
    }
    table = bench.render_markdown(payload)
    assert "| Scenario | 1,000 files | 5,000 files |" in table
    assert "| python, cycle | 1.2 s / 8 MB | 3.0 s / n/a |" in table
    # The shipped baseline renders without error.
    shipped = Path(__file__).resolve().parents[1] / "benchmarks" / "baseline.json"
    assert "20,000 files" in bench.render_markdown(json.loads(shipped.read_text(encoding="utf-8")))


def test_performance_page_table_matches_baseline():
    """docs/performance.md embeds the generated table; no hand-typed numbers."""
    import json

    bench = _load()
    root = Path(__file__).resolve().parents[1]
    table = bench.render_markdown(
        json.loads((root / "benchmarks" / "baseline.json").read_text(encoding="utf-8"))
    )
    page = (root / "docs" / "performance.md").read_text(encoding="utf-8")
    assert table in page
