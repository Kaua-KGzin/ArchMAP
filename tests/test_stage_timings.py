from __future__ import annotations

import time

from archmap.core import analyze_project
from archmap.core.perf.synthetic import generate_project
from archmap.core.perf.timing import StageTimer


def test_stage_timings_present(tmp_path):
    generate_project(tmp_path, 30)
    t = analyze_project(tmp_path, use_cache=False)["metrics"]["analysisQuality"]["timingsMs"]
    assert {
        "discover", "parse", "cycles", "impact", "risk",
        "testMapping", "centrality", "findings",
    } <= t.keys()


def test_stage_timer_accumulates_and_rounds():
    timer = StageTimer()
    with timer.stage("a"):
        time.sleep(0.01)
    with timer.stage("a"):
        pass
    d = timer.as_dict()
    assert list(d) == ["a"]
    assert d["a"] >= 10.0
    assert d["a"] == round(d["a"], 1)
