"""Analysis-quality metrics: how much of the project ArchMAP actually understood.

Every number ArchMAP reports (health score, cycles, blast radius) is only as
trustworthy as the parse behind it. Files that fail to parse, can't be
decoded, or exceed the size limit silently vanish from the graph, and
unresolved imports leave edges missing. This module turns those gaps into
explicit metrics (``metrics.analysisQuality``) and ``QUAL-*`` findings so a
human, a CI gate, or an AI agent can tell a clean graph from a partial one.
"""

from __future__ import annotations

from typing import Any, TypedDict

from archmap.types import Finding

# Per-file failure findings beyond this count collapse into one aggregate finding.
MAX_FAILURE_FINDINGS = 25
# Languages with fewer imports than this are too small to judge resolution on.
MIN_IMPORTS_FOR_LANGUAGE_WARNING = 5
LOW_LANGUAGE_RESOLUTION = 0.5


class ParseFailure(TypedDict):
    file: str
    language: str
    error: str


class ParseDiagnostics(TypedDict, total=False):
    """Raw counters collected by ``parse_project`` while reading the project."""

    discovered: int
    oversized: list[str]
    decodeErrors: list[str]
    parseFailures: list[ParseFailure]
    timingsMs: dict[str, float]


def empty_diagnostics() -> ParseDiagnostics:
    return {
        "discovered": 0,
        "oversized": [],
        "decodeErrors": [],
        "parseFailures": [],
        "timingsMs": {},
    }


def build_analysis_quality(
    diagnostics: ParseDiagnostics | None,
    parsed_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize parse coverage, failures, and per-language resolution.

    ``coverage`` is the share of discovered source files that made it into
    the graph. ``confidence`` blends coverage with import resolution
    (``coverage * (0.6 + 0.4 * resolutionRate)``): a fully parsed project
    whose imports never resolve still has a graph with missing edges.
    """
    diag = diagnostics or empty_diagnostics()
    oversized = sorted(diag.get("oversized", []))
    decode_errors = sorted(diag.get("decodeErrors", []))
    failures = sorted(diag.get("parseFailures", []), key=lambda item: item["file"])

    parsed_count = len(parsed_files)
    discovered = max(
        int(diag.get("discovered", 0)),
        parsed_count + len(failures) + len(decode_errors) + len(oversized),
    )
    coverage = round(parsed_count / discovered, 3) if discovered else 1.0

    languages: dict[str, dict[str, Any]] = {}
    total_imports = 0
    resolved_imports = 0
    for parsed in parsed_files:
        lang = str(parsed.get("language", "unknown"))
        entry = languages.setdefault(
            lang, {"files": 0, "imports": 0, "resolved": 0, "failures": 0}
        )
        entry["files"] += 1
        entry["imports"] += int(parsed.get("importsTotal", 0))
        entry["resolved"] += int(parsed.get("importsResolved", 0))
    for failure in failures:
        entry = languages.setdefault(
            failure["language"], {"files": 0, "imports": 0, "resolved": 0, "failures": 0}
        )
        entry["failures"] += 1
    for entry in languages.values():
        imports = entry["imports"]
        entry["resolutionRate"] = round(entry["resolved"] / imports, 3) if imports else 1.0
        total_imports += imports
        resolved_imports += entry["resolved"]

    resolution = round(resolved_imports / total_imports, 3) if total_imports else 1.0
    confidence = round(coverage * (0.6 + 0.4 * resolution), 3)
    if confidence >= 0.9:
        level = "high"
    elif confidence >= 0.7:
        level = "medium"
    else:
        level = "low"

    warnings: list[str] = []
    if failures:
        warnings.append(f"{len(failures)} file(s) failed to parse and are missing from the graph")
    if decode_errors:
        warnings.append(f"{len(decode_errors)} file(s) could not be decoded as UTF-8")
    if oversized:
        warnings.append(f"{len(oversized)} file(s) skipped for exceeding max_file_size_bytes")
    for lang, entry in sorted(languages.items()):
        if (
            entry["imports"] >= MIN_IMPORTS_FOR_LANGUAGE_WARNING
            and entry["resolutionRate"] < LOW_LANGUAGE_RESOLUTION
        ):
            warnings.append(
                f"{lang}: only {round(entry['resolutionRate'] * 100)}% of imports resolved"
            )

    return {
        "filesDiscovered": discovered,
        "filesParsed": parsed_count,
        "coverage": coverage,
        "resolutionRate": resolution,
        "confidence": confidence,
        "confidenceLevel": level,
        "parseFailureCount": len(failures),
        "parseFailures": failures[:100],
        "decodeFailureCount": len(decode_errors),
        "decodeFailures": decode_errors[:100],
        "oversizedSkippedCount": len(oversized),
        "oversizedSkipped": oversized[:100],
        "languages": dict(sorted(languages.items())),
        "warnings": warnings,
        "timingsMs": dict(diag.get("timingsMs", {})),
    }


def build_quality_findings(quality: dict[str, Any]) -> list[Finding]:
    """Turn analysis-quality gaps into ``QUAL-*`` findings."""
    findings: list[Finding] = []

    def _add(
        category: str, severity: str, message: str, evidence: list[str], file: str | None = None
    ) -> None:
        finding = Finding(
            id=f"QUAL-{len(findings) + 1:03d}",
            domain="quality",
            category=category,
            severity=severity,
            confidence=1.0,
            message=message,
            evidence=evidence,
        )
        if file:
            finding["file"] = file
        findings.append(finding)

    failures: list[ParseFailure] = quality.get("parseFailures", [])
    failure_count = int(quality.get("parseFailureCount", len(failures)))
    for failure in failures[:MAX_FAILURE_FINDINGS]:
        _add(
            "parse_failure",
            "medium",
            f"Parse failure: {failure['file']} is missing from the graph",
            [f"Language: {failure['language']}", f"Error: {failure['error']}"],
            file=failure["file"],
        )
    if failure_count > MAX_FAILURE_FINDINGS:
        _add(
            "parse_failure",
            "medium",
            f"{failure_count - MAX_FAILURE_FINDINGS} more file(s) failed to parse",
            ["See metrics.analysisQuality.parseFailures"],
        )

    decode_count = int(quality.get("decodeFailureCount", 0))
    if decode_count:
        sample = quality.get("decodeFailures", [])[:5]
        _add(
            "decode_failure",
            "low",
            f"{decode_count} source file(s) are not valid UTF-8 and were skipped",
            [f"File: {item}" for item in sample],
        )

    oversized_count = int(quality.get("oversizedSkippedCount", 0))
    if oversized_count:
        sample = quality.get("oversizedSkipped", [])[:5]
        _add(
            "oversized_skipped",
            "info",
            f"{oversized_count} file(s) skipped for exceeding analysis.max_file_size_bytes",
            [f"File: {item}" for item in sample],
        )

    for lang, entry in quality.get("languages", {}).items():
        if (
            int(entry.get("imports", 0)) >= MIN_IMPORTS_FOR_LANGUAGE_WARNING
            and float(entry.get("resolutionRate", 1.0)) < LOW_LANGUAGE_RESOLUTION
        ):
            _add(
                "low_resolution",
                "medium",
                f"{lang}: only {round(float(entry['resolutionRate']) * 100)}% of imports "
                "resolved; dependents and blast radius are under-reported",
                [f"Imports: {entry['imports']}", f"Resolved: {entry['resolved']}"],
            )

    return findings
