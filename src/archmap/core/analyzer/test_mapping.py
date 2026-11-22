"""Map test files to the project files they exercise.

A source file counts as tested when a test file imports it, or when a test
file is named after it by the language's convention (``test_foo.py``,
``foo_test.go``, ``foo.spec.ts``, ``FooTest.java``). The naming rule matters
for Go and Java, whose tests share the package under test and often import
nothing from it.

This is a static, structural signal: "some test refers to this file", not
line coverage. It is reported beside the risk score, never folded into it.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from archmap.types import Finding
from archmap.utils.file_utils import (
    SUPPORTED_EXTENSIONS,
    normalize_file_id,
    to_file_id,
    walk_project_files,
)

TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__", "spec", "specs"})

# Stem extractors, tried in order; each returns the name of the file under test.
_STEM_PATTERNS = (
    re.compile(r"^test_(?P<stem>.+)\.py$"),
    re.compile(r"^(?P<stem>.+)_test\.(?:py|go)$"),
    re.compile(r"^(?P<stem>.+)\.(?:test|spec)\.[cm]?[jt]sx?$"),
    re.compile(r"^(?P<stem>.+?)Tests?\.(?:java|kt|cs)$"),
)

# How many untested high-risk files become findings, so the list stays short.
MAX_TEST_FINDINGS = 10
# Mapping is static and cannot see indirect coverage (a test that exercises a
# file through another module), so a gap is likely, not certain.
_UNTESTED_CONFIDENCE = 0.7


def is_test_file(file_id: str) -> bool:
    normalized = normalize_file_id(file_id)
    parts = normalized.split("/")
    if any(part.casefold() in TEST_DIR_NAMES for part in parts[:-1]):
        return True
    return _test_stem(parts[-1]) is not None


def discover_test_files(
    project_root: Path,
    analysis: Mapping[str, Any] | None = None,
    exclude: Iterable[str] = (),
) -> dict[str, Path]:
    """Test files under ``project_root`` (file id -> path), ``tests/`` included.

    Honours the same ``ignore_dirs`` and ``respect_gitignore`` settings as
    source discovery; only the built-in test directory names are walked
    into. Ids in ``exclude`` (files already in the graph) are left out.
    """
    analysis = analysis or {}
    skip = set(exclude)
    found: dict[str, Path] = {}
    for path in walk_project_files(
        project_root,
        analysis.get("ignore_dirs") or None,
        respect_gitignore=bool(analysis.get("respect_gitignore", True)),
        unignore=TEST_DIR_NAMES,
    ):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        file_id = to_file_id(project_root, path)
        if file_id not in skip and is_test_file(file_id):
            found[file_id] = path
    return found


def _test_stem(basename: str) -> str | None:
    for pattern in _STEM_PATTERNS:
        match = pattern.match(basename)
        if match:
            return match.group("stem")
    return None


def _source_stem(file_id: str) -> str:
    # Only the extension goes: `user.service.ts` -> `user.service`, matching
    # the stem `user.service.spec.ts` yields.
    return posixpath.splitext(posixpath.basename(file_id))[0]


def _dir_parts_without_test_dirs(file_id: str) -> tuple[str, ...]:
    parts = normalize_file_id(file_id).split("/")[:-1]
    return tuple(p for p in parts if p.casefold() not in TEST_DIR_NAMES)


def _mirror_score(test_id: str, source_id: str) -> int:
    """Length of the shared directory suffix once test dirs are removed.

    ``tests/users/test_models.py`` and ``app/users/models.py`` share
    ``users``; ``src/test/java/acme/XTest.java`` and
    ``src/main/java/acme/X.java`` share ``java/acme``.
    """
    test_dirs = _dir_parts_without_test_dirs(test_id)
    source_dirs = normalize_file_id(source_id).split("/")[:-1]
    score = 0
    for a, b in zip(reversed(test_dirs), reversed(source_dirs), strict=False):
        if a.casefold() != b.casefold():
            break
        score += 1
    return score


def _convention_target(test_id: str, by_stem: Mapping[str, list[str]]) -> str | None:
    stem = _test_stem(posixpath.basename(test_id))
    if stem is None:
        return None
    candidates = by_stem.get(stem.casefold(), [])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    scored = sorted(((_mirror_score(test_id, c), c) for c in candidates), reverse=True)
    best, runner_up = scored[0], scored[1]
    return best[1] if best[0] > runner_up[0] else None


def build_test_mapping(
    file_ids: Iterable[str], test_dependencies: Mapping[str, Iterable[str]]
) -> dict[str, list[str]]:
    """Source file -> sorted test files that exercise it.

    ``file_ids`` are the graph's files (test files among them are dropped
    from the result); ``test_dependencies`` maps each test file to the
    project files it imports.
    """
    sources = sorted({fid for fid in file_ids if not is_test_file(fid)})
    mapping: dict[str, set[str]] = {fid: set() for fid in sources}
    by_stem: dict[str, list[str]] = {}
    for fid in sources:
        by_stem.setdefault(_source_stem(fid).casefold(), []).append(fid)

    for test_id, deps in test_dependencies.items():
        for dep in deps:
            if dep in mapping:
                mapping[dep].add(test_id)
        target = _convention_target(test_id, by_stem)
        if target is not None:
            mapping[target].add(test_id)

    return {fid: sorted(tests) for fid, tests in mapping.items()}


def summarize_test_mapping(
    mapping: Mapping[str, list[str]], test_file_count: int
) -> dict[str, Any]:
    tested = sum(1 for tests in mapping.values() if tests)
    total = len(mapping)
    return {
        "testFiles": test_file_count,
        "sourceFiles": total,
        "testedFiles": tested,
        "untestedFiles": total - tested,
        "testedRatio": round(tested / total, 3) if total else 1.0,
    }


def build_test_findings(
    mapping: Mapping[str, list[str]], risks: Mapping[str, Any], test_file_count: int
) -> list[Finding]:
    """``TEST-*`` findings: the highest-risk files that no test refers to.

    A project without any test file gets none: one finding per file would
    only restate "there are no tests", which ``metrics.testMapping`` says.
    """
    if test_file_count == 0:
        return []
    findings: list[Finding] = []
    for entry in risks.get("top_risk_files", []):
        file_id = entry.get("file")
        if file_id not in mapping or mapping[file_id]:
            continue
        findings.append(
            Finding(
                id=f"TEST-{len(findings) + 1:03d}",
                domain="testing",
                category="untested_critical_file",
                severity="medium",
                confidence=_UNTESTED_CONFIDENCE,
                message=f"High-risk file has no test referring to it: {file_id}",
                evidence=[
                    f"Risk score: {entry.get('riskScore')}",
                    "No test file imports it or is named after it",
                ],
                file=file_id,
                remediation=(
                    "Add a test that exercises this file directly; it is among "
                    "the files whose changes reach the most of the project."
                ),
            )
        )
        if len(findings) >= MAX_TEST_FINDINGS:
            break
    return findings
