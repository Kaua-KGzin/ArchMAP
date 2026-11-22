"""Test -> source mapping: which project files have tests, and which do not."""

from __future__ import annotations

import pytest

from archmap.core.analyzer.test_mapping import (
    build_test_findings,
    build_test_mapping,
    is_test_file,
)


@pytest.mark.parametrize(
    "file_id",
    [
        "tests/test_parser.py",
        "pkg/parser_test.py",
        "src/app/user.service.spec.ts",
        "src/ui/Button.test.tsx",
        "web/__tests__/home.js",
        "internal/store/store_test.go",
        "src/test/java/com/acme/UserServiceTest.java",
        "Acme.Tests/UserServiceTests.cs",
        "spec/models/user_spec.rb.py",
        "tests/conftest.py",
        # .NET keeps tests in their own project, named after the one tested.
        "Archlab.Backend.Tests/Integration/ApiFactory.cs",
        "src/Acme.UnitTests/Helpers.cs",
        "Acme.IntegrationTests/Fixture.cs",
    ],
)
def test_recognises_test_files(file_id):
    assert is_test_file(file_id)


@pytest.mark.parametrize(
    "file_id",
    [
        "src/parser.py",
        "src/testing_utils.py",
        "src/latest.ts",
        "src/contest/entry.go",
        "src/main/java/com/acme/UserService.java",
        "src/attestation.cs",
        "Acme.Contests/Entry.cs",
        "Acme.Testing.Abstractions/Clock.cs",
    ],
)
def test_does_not_flag_source_files(file_id):
    assert not is_test_file(file_id)


def test_import_edges_map_tests_to_sources():
    mapping = build_test_mapping(
        ["src/parser.py", "src/graph.py"],
        {"tests/test_anything.py": ["src/parser.py"]},
    )
    assert mapping == {"src/parser.py": ["tests/test_anything.py"], "src/graph.py": []}


def test_naming_convention_maps_tests_that_do_not_import_their_target():
    # Go and Java tests share the package of the code under test, so they
    # often import nothing from it.
    mapping = build_test_mapping(
        ["internal/store/store.go", "src/main/java/acme/UserService.java", "src/ui/Button.tsx"],
        {
            "internal/store/store_test.go": [],
            "src/test/java/acme/UserServiceTest.java": [],
            "src/ui/Button.test.tsx": [],
        },
    )
    assert mapping["internal/store/store.go"] == ["internal/store/store_test.go"]
    assert mapping["src/main/java/acme/UserService.java"] == [
        "src/test/java/acme/UserServiceTest.java"
    ]
    assert mapping["src/ui/Button.tsx"] == ["src/ui/Button.test.tsx"]


def test_naming_convention_handles_dotted_basenames():
    # NestJS/Angular: `user.service.ts` is tested by `user.service.spec.ts`,
    # and must not be confused with `user.controller.ts`.
    mapping = build_test_mapping(
        ["src/users/user.service.ts", "src/users/user.controller.ts"],
        {"test/users/user.service.spec.ts": []},
    )
    assert mapping["src/users/user.service.ts"] == ["test/users/user.service.spec.ts"]
    assert mapping["src/users/user.controller.ts"] == []


def test_ambiguous_name_prefers_the_mirrored_directory():
    mapping = build_test_mapping(
        ["app/users/models.py", "app/orders/models.py"],
        {"tests/users/test_models.py": []},
    )
    assert mapping["app/users/models.py"] == ["tests/users/test_models.py"]
    assert mapping["app/orders/models.py"] == []


def test_unresolvable_ambiguity_maps_nothing():
    mapping = build_test_mapping(
        ["a/models.py", "b/models.py"],
        {"tests/test_models.py": []},
    )
    assert mapping == {"a/models.py": [], "b/models.py": []}


def test_test_files_are_not_part_of_the_source_population():
    mapping = build_test_mapping(
        ["src/a.ts", "src/a.spec.ts"],
        {"src/a.spec.ts": ["src/a.ts"]},
    )
    assert set(mapping) == {"src/a.ts"}


def _project(tmp_path, with_tests: bool):
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("from pkg import leaf\n")
    (pkg / "leaf.py").write_text("X = 1\n")
    if with_tests:
        (tmp_path / "tests").mkdir()
        # Named after no source file, so only the import can map it: a src/
        # layout package imported from a tests/ dir that has no __init__.py.
        (tmp_path / "tests" / "test_behaviour.py").write_text("from pkg.core import *\n")
    return tmp_path


def test_analysis_maps_tests_in_ignored_dirs_without_graphing_them(tmp_path):
    from archmap.core import analyze_project

    report = analyze_project(_project(tmp_path, with_tests=True), use_cache=False)
    nodes = {n["id"]: n for n in report["nodes"] if n.get("type") == "file"}

    assert "tests/test_behaviour.py" not in nodes
    assert nodes["src/pkg/core.py"]["testedBy"] == ["tests/test_behaviour.py"]
    assert nodes["src/pkg/leaf.py"]["testedBy"] == []
    summary = report["metrics"]["testMapping"]
    assert summary["testFiles"] == 1
    assert summary["testedFiles"] == 1


def test_test_mapping_leaves_risk_scores_and_health_unchanged(tmp_path):
    from archmap.core import analyze_project

    with_tests = analyze_project(_project(tmp_path / "a", with_tests=True), use_cache=False)
    without = analyze_project(_project(tmp_path / "b", with_tests=False), use_cache=False)

    def scores(report):
        return {e["file"]: e["riskScore"] for e in report["risks"]["top_risk_files"]}

    assert scores(with_tests) == scores(without)
    assert (
        with_tests["metrics"]["architectureHealthScore"]
        == without["metrics"]["architectureHealthScore"]
    )
    assert without["metrics"]["testMapping"]["testFiles"] == 0


def test_editing_a_test_file_invalidates_the_report_cache(tmp_path):
    # testMapping is part of the cached report, so a test file is an input.
    from archmap.cache import compute_fingerprint

    root = _project(tmp_path, with_tests=True)
    config = {"analysis": {"ignore_dirs": []}}
    before = compute_fingerprint(root, config)
    (root / "tests" / "test_behaviour.py").write_text(
        "from pkg.core import *\nfrom pkg import leaf\n"
    )
    assert compute_fingerprint(root, config) != before


def test_mcp_list_findings_can_filter_the_testing_domain():
    from archmap.cli.mcp_server import _TOOLS

    tool = next(t for t in _TOOLS if t["name"] == "list_findings")
    assert "testing" in tool["inputSchema"]["properties"]["domain"]["enum"]
    assert "TEST-*" in tool["description"]


def test_findings_flag_untested_top_risk_files_only():
    risks = {
        "top_risk_files": [
            {"file": "src/core.py", "riskScore": 40},
            {"file": "src/tested.py", "riskScore": 30},
        ]
    }
    mapping = {"src/core.py": [], "src/tested.py": ["tests/test_tested.py"], "src/leaf.py": []}
    findings = build_test_findings(mapping, risks, test_file_count=1)

    assert [f["file"] for f in findings] == ["src/core.py"]
    finding = findings[0]
    assert finding["id"] == "TEST-001"
    assert finding["domain"] == "testing"
    assert finding["category"] == "untested_critical_file"
    assert 0 < finding["confidence"] < 1


def test_no_findings_when_the_project_has_no_tests_at_all():
    risks = {"top_risk_files": [{"file": "src/core.py", "riskScore": 40}]}
    assert build_test_findings({"src/core.py": []}, risks, test_file_count=0) == []
