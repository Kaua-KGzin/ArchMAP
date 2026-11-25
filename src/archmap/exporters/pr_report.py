"""Render an architecture delta (``diff_reports`` output) as a PR comment.

Pure function, no I/O: the GitHub Action writes the result to the job summary
and upserts it as one comment, found again by ``PR_REPORT_MARKER``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from archmap import __version__

PR_REPORT_MARKER = "<!-- archmap:pr-report -->"
MAX_ROWS = 15
# GitHub rejects comment bodies over 65,536 characters; stay well below it.
MAX_CHARS = 60_000
_MAX_CELL = 300


def _cell(text: object) -> str:
    value = " ".join(str(text).split())
    if len(value) > _MAX_CELL:
        value = value[: _MAX_CELL - 1] + "…"
    return value.replace("|", "\\|")


def _where(finding: dict[str, Any]) -> str:
    if finding.get("file"):
        return f"`{_cell(finding['file'])}`"
    if finding.get("source") and finding.get("target"):
        return f"`{_cell(finding['source'])}` → `{_cell(finding['target'])}`"
    return "—"


def _finding_table(title: str, findings: list[dict[str, Any]]) -> list[str]:
    if not findings:
        return []
    lines = [f"#### {title} ({len(findings)})", "", "| Severity | Finding | Where |",
             "|---|---|---|"]
    for finding in findings[:MAX_ROWS]:
        lines.append(
            f"| {_cell(finding.get('severity', ''))} | {_cell(finding.get('message', ''))} "
            f"| {_where(finding)} |"
        )
    lines.extend(_more(len(findings)))
    lines.append("")
    return lines


def _more(total: int) -> list[str]:
    return ["", f"…and {total - MAX_ROWS} more"] if total > MAX_ROWS else []


def _percent(ratio: float) -> str:
    return f"{ratio * 100:.1f}%"


def _summary(diff: dict[str, Any]) -> list[str]:
    architecture = diff.get("architecture", {})
    base, head = architecture.get("baseHealth"), architecture.get("headHealth")
    delta = architecture.get("healthDelta", 0) or 0
    grades = diff.get("grades", {})
    line = f"Health **{base} → {head}**"
    if grades.get("base") and grades.get("head"):
        line += f" ({grades['base']} → {grades['head']})"
    if delta:
        line += f" · {'▲' if delta > 0 else '▼'} {abs(delta)}"
    parts = [line]

    tests = diff.get("tests", {})
    base_ratio, head_ratio = tests.get("baseTestedRatio"), tests.get("headTestedRatio")
    if base_ratio is not None and head_ratio is not None:
        parts.append(f"Tested files **{_percent(base_ratio)} → {_percent(head_ratio)}**")
    cycles = diff.get("cycles", {})
    if cycles:
        parts.append(f"Cycles {cycles.get('base', 0)} → {cycles.get('head', 0)}")
    findings = diff.get("findings")
    if diff.get("findingsComparable") and isinstance(findings, dict):
        parts.append(f"Findings +{len(findings['new'])} / −{len(findings['resolved'])}")
    return [" · ".join(parts), ""]


def _lost_coverage(entries: Iterable[dict[str, Any]]) -> list[str]:
    entries = list(entries)
    if not entries:
        return []
    lines = [f"#### Lost test coverage ({len(entries)})", ""]
    for entry in entries[:MAX_ROWS]:
        tests = ", ".join(f"`{_cell(t)}`" for t in entry.get("testedBy", [])[:3])
        lines.append(f"- `{_cell(entry['file'])}` (was tested by {tests})")
    lines.extend(_more(len(entries)))
    lines.append("")
    return lines


def _has_changes(diff: dict[str, Any]) -> bool:
    findings = diff.get("findings") or {}
    return bool(
        diff.get("architecture", {}).get("healthDelta")
        or findings.get("new")
        or findings.get("resolved")
        or diff.get("tests", {}).get("lostCoverage")
        or diff.get("cycles", {}).get("delta")
    )


def render_pr_report(diff: dict[str, Any], *, base_label: str, head_label: str) -> str:
    """Markdown for one sticky PR comment; always starts with ``PR_REPORT_MARKER``."""
    lines = [PR_REPORT_MARKER, "### ArchMAP · architecture delta", ""]
    lines.extend(_summary(diff))

    if not diff.get("findingsComparable"):
        lines.extend([
            "> The base report predates finding comparison (written by ArchMAP 1.5.0 or "
            "older), so new and resolved findings are not listed.",
            "",
        ])
    elif not _has_changes(diff):
        lines.extend(["No architecture changes detected.", ""])

    findings = diff.get("findings") or {}
    bottlenecks = (diff.get("bottlenecks") or {}).get("new", [])
    lines.extend(_finding_table("New findings", findings.get("new", [])))
    lines.extend(_finding_table("Resolved", findings.get("resolved", [])))
    lines.extend(_finding_table("New structural bottlenecks", bottlenecks))
    lines.extend(_lost_coverage(diff.get("tests", {}).get("lostCoverage", [])))

    footer = f"<sub>ArchMAP {__version__} · base `{base_label}` → head `{head_label}`</sub>"
    body = "\n".join(lines)
    limit = MAX_CHARS - len(footer) - 2
    if len(body) > limit:
        body = body[: limit - 40].rsplit("\n", 1)[0] + "\n\n…(report truncated)"
    return f"{body}\n{footer}\n"
