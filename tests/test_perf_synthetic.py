from __future__ import annotations

from archmap.core import analyze_project
from archmap.core.perf.synthetic import generate_project, generate_sources


def test_generate_project_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate_project(a, 50, shape="layered", seed=1)
    generate_project(b, 50, shape="layered", seed=1)
    assert sorted(p.read_text() for p in a.rglob("*.py")) == sorted(
        p.read_text() for p in b.rglob("*.py")
    )


def test_layered_shape_has_no_cycles(tmp_path):
    generate_project(tmp_path, 200, shape="layered")
    assert analyze_project(tmp_path, use_cache=False)["cycles"] == []


def test_cycle_shape_has_cycles(tmp_path):
    generate_project(tmp_path, 30, shape="cycle")
    assert analyze_project(tmp_path, use_cache=False)["cycles"]


def test_typescript_generator_resolves_imports(tmp_path):
    generate_project(tmp_path, 100, language="typescript", shape="hub")
    report = analyze_project(tmp_path, use_cache=False)
    assert report["metrics"]["analysisQuality"]["resolutionRate"] >= 0.99
    assert report["metrics"]["totalDependencies"] > 100


def test_generate_project_matches_generate_sources(tmp_path):
    for language, ext in (("python", "py"), ("typescript", "ts")):
        root = tmp_path / language
        generate_project(root, 40, language=language, shape="hub", seed=3)
        expected = generate_sources(40, language=language, shape="hub", seed=3)
        on_disk = {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in root.rglob(f"*.{ext}")
        }
        assert on_disk == expected
        assert len(expected) == 40
