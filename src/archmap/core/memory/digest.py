from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from archmap.core.exposure.network_diff import Observation, normalize_observations
from archmap.core.exposure.snapshots import Snapshot

# Stored under the same `.archmap/` convention archmap.cache already uses for
# the on-disk analysis cache, so a project only needs one generated-artifacts
# directory to gitignore (or commit — see docs/cli/memory.md).
DEFAULT_MEMORY_RELATIVE_PATH = ".archmap/memory.md"

_MAX_LIST_ITEMS = 10
_TIMESTAMP_LINE = re.compile(r"^_Generated:.*$", re.MULTILINE)

# An observation is worth the digest's tokens when the network itself rates
# the port risky, when correlation rated the finding severe, when a config
# literal in the codebase actually points at it, or when it breaks a
# declared `[network.rules]` boundary. Everything else is just an open port.
_NOTABLE_SEVERITIES = frozenset({"high", "critical"})
_NOTABLE_MIN_CONFIDENCE = 0.7


def digest_changed(existing: str | None, new: str) -> bool:
    """True if `new` differs from `existing` in anything but the timestamp.

    Lets callers skip rewriting the memory file (and touching its mtime,
    which would show up as a no-op git diff on every PostToolUse hook run)
    when nothing about the project's architecture actually changed.
    """
    if existing is None:
        return True
    return _TIMESTAMP_LINE.sub("", existing) != _TIMESTAMP_LINE.sub("", new)


def _is_notable(observation: Observation) -> bool:
    if observation["drift"] is not None:
        return True
    if (observation["severity"] or "") in _NOTABLE_SEVERITIES:
        return True
    if (observation["riskLevel"] or "") in _NOTABLE_SEVERITIES:
        return True
    confidence = observation["confidence"]
    return confidence is not None and confidence >= _NOTABLE_MIN_CONFIDENCE


def _observation_rank(observation: Observation) -> tuple[int, float, str, int]:
    severity_rank = 1 if (observation["severity"] or "") in _NOTABLE_SEVERITIES else 0
    risk_rank = 1 if (observation["riskLevel"] or "") in _NOTABLE_SEVERITIES else 0
    return (
        -(severity_rank + risk_rank),
        -(observation["confidence"] or 0.0),
        observation["host"],
        observation["port"],
    )


def render_network_section(snapshot: Snapshot) -> list[str]:
    """Render the network-exposure part of the digest from a stored snapshot.

    Works off whichever snapshot the project last captured — a bare
    `netscan` (ports and their static risk) or a correlated `expose` (adds
    severity, confidence, and `[network.rules]` drift). The observation list
    is filtered to what an agent would actually act on, so a /24 with fifty
    boring open ports doesn't crowd out the code-side digest.
    """
    report = snapshot["report"]
    observations = normalize_observations(report)
    drift_violations = report.get("driftViolations", [])
    notable = sorted((o for o in observations if _is_notable(o)), key=_observation_rank)

    lines = [
        "## Network exposure",
        (
            f"_Snapshot: {snapshot['capturedAt']} — target `{snapshot['target']}` "
            f"(`archmap {snapshot['kind']}`)_"
        ),
        (
            f"- Open ports: {len(observations)} | "
            f"Notable: {len(notable)} | "
            f"Network rule violations: {len(drift_violations)}"
        ),
        "",
    ]

    if drift_violations:
        lines.append("### Network rule violations")
        for violation in drift_violations[:_MAX_LIST_ITEMS]:
            lines.append(f"- {violation.get('message', '')}")
        if len(drift_violations) > _MAX_LIST_ITEMS:
            lines.append(f"- ...and {len(drift_violations) - _MAX_LIST_ITEMS} more")
        lines.append("")

    if notable:
        lines.append("### Notable exposed services")
        for observation in notable[:_MAX_LIST_ITEMS]:
            details = []
            if observation["severity"]:
                details.append(f"severity {observation['severity']}")
            if observation["riskLevel"]:
                details.append(f"port risk {observation['riskLevel']}")
            if observation["confidence"] is not None:
                details.append(f"confidence {round(observation['confidence'] * 100)}%")
            suffix = f" — {', '.join(details)}" if details else ""
            lines.append(
                f"- `{observation['host']}:{observation['port']}` "
                f"({observation['protocol']}) {observation['service']}{suffix}"
            )
        if len(notable) > _MAX_LIST_ITEMS:
            lines.append(f"- ...and {len(notable) - _MAX_LIST_ITEMS} more")
        lines.append("")

    return lines


def generate_memory_digest(
    report: dict[str, Any], network_snapshot: Snapshot | None = None
) -> str:
    """Render a compact, token-efficient markdown snapshot of an analyzed
    project's architecture — health, risks, cycles, violations.

    Meant to be read by an AI coding agent (Claude Code and friends) at the
    start of a session instead of re-exploring the codebase from scratch:
    every fact here is already computed by `archmap analyze`, this just
    condenses it into prose an agent can skim in one read. Deterministic
    given the same report, so re-running `archmap memory` after a no-op
    change reproduces byte-identical output.

    When `network_snapshot` is given (the project's most recent
    `archmap expose`/`netscan --snapshot`), a network-exposure section is
    folded in, so the session-start context covers both domains without a
    second command or MCP call. Projects that never scan get the exact same
    digest they got before — the section is simply absent.
    """
    metrics = report.get("metrics", {})
    risks = report.get("risks", {})
    architecture = report.get("architecture", {})
    cycles = report.get("cycles", [])
    health = architecture.get("health", {})
    style = architecture.get("detectedStyle", {})

    lines: list[str] = [
        "# ArchMAP Project Memory",
        "",
        "_Auto-generated by `archmap memory` — do not edit by hand; "
        "regenerate with `archmap memory`._",
        f"_Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Health",
        (
            f"- Score: **{health.get('score', 0)}/100** ({health.get('grade', '?')}) — "
            f"{health.get('summary', '')}"
        ),
        f"- Style: **{style.get('name', 'unknown')}** (confidence {style.get('confidence', 0)})",
        (
            f"- Files: {metrics.get('filesAnalyzed', 0)} | "
            f"Dependencies: {metrics.get('totalDependencies', 0)} | "
            f"External packages: {metrics.get('externalDependencies', 0)}"
        ),
        (
            f"- Cycles: {len(cycles)} | "
            f"God modules: {len(risks.get('god_modules', []))} | "
            f"Layer violations: {len(risks.get('layer_violations', []))} | "
            f"Custom rule violations: {len(architecture.get('ruleViolations', []))}"
        ),
    ]
    if health.get("drivers"):
        lines.append(f"- Score drivers: {', '.join(health['drivers'])}")
    quality = metrics.get("analysisQuality")
    if quality:
        # Timings are deliberately left out: they change on every run and would
        # defeat digest_changed()'s no-op detection.
        lines.append(
            f"- Analysis confidence: **{quality.get('confidenceLevel', '?')}** "
            f"({round(float(quality.get('confidence', 1.0)) * 100)}%; "
            f"{quality.get('filesParsed', 0)}/{quality.get('filesDiscovered', 0)} files parsed, "
            f"import resolution {round(float(quality.get('resolutionRate', 1.0)) * 100)}%)"
        )
        for warning in quality.get("warnings", [])[:_MAX_LIST_ITEMS]:
            lines.append(f"- Warning: {warning} — the graph is incomplete there")
    lines.append("")

    detected_layers = architecture.get("detectedLayers", [])
    if detected_layers:
        lines += ["## Detected layers", ", ".join(detected_layers), ""]

    top_risk_files = risks.get("top_risk_files", [])[:_MAX_LIST_ITEMS]
    if top_risk_files:
        lines.append("## Top risk files")
        for item in top_risk_files:
            signals = ", ".join(item.get("signals", [])) or "none"
            lines.append(
                f"- `{item.get('file')}` — risk {item.get('riskScore', 0)} "
                f"(dependents: {item.get('dependents', 0)}, "
                f"outgoing: {item.get('outgoing', 0)}; {signals})"
            )
        lines.append("")

    if cycles:
        lines.append("## Circular dependencies")
        for cycle in cycles[:_MAX_LIST_ITEMS]:
            lines.append("- " + " → ".join(cycle) + " → (back to start)")
        if len(cycles) > _MAX_LIST_ITEMS:
            lines.append(f"- ...and {len(cycles) - _MAX_LIST_ITEMS} more")
        lines.append("")

    layer_violations = risks.get("layer_violations", [])[:_MAX_LIST_ITEMS]
    if layer_violations:
        lines.append("## Layer violations")
        for violation in layer_violations:
            lines.append(
                f"- `{violation['source']}` ({violation['sourceLayer']}) → "
                f"`{violation['target']}` ({violation['targetLayer']}) — {violation['rule']}"
            )
        lines.append("")

    rule_violations = architecture.get("ruleViolations", [])[:_MAX_LIST_ITEMS]
    if rule_violations:
        lines.append("## Custom architecture rule violations")
        for violation in rule_violations:
            lines.append(f"- {violation['message']}")
        lines.append("")

    god_modules = risks.get("god_modules", [])[:_MAX_LIST_ITEMS]
    if god_modules:
        lines.append("## God modules")
        for module in god_modules:
            lines.append(f"- `{module['file']}` — {module['outgoing']} outgoing dependencies")
        lines.append("")

    if network_snapshot is not None:
        lines += render_network_section(network_snapshot)

    lines += [
        "## For AI agents",
        (
            "- This file is a pre-computed snapshot — trust it over re-exploring the "
            "codebase from scratch. It refreshes automatically after edits if the "
            "PostToolUse hook from `archmap memory --help` is wired up; otherwise "
            "re-run `archmap memory` after structural changes."
        ),
        (
            "- For a specific task, call the `archmap mcp` tool `get_relevant_context` "
            "(or `archmap context \"<task>\"`) to get the files to read in order. For "
            "live detail use `get_file_context`, `impact_analysis`, `trace_reachability`, "
            "`run_checks`, `diff_architecture`, `list_findings`, `get_analysis_quality`; "
            "for binaries and unknown files, `inspect_path`, `extract_strings`, `hexdump`."
        ),
    ]
    if network_snapshot is not None:
        lines.append(
            "- The network section reflects the last stored scan, not the live network. "
            "Re-scan with `archmap expose <target> --snapshot`, or compare it against "
            "an earlier scan with `archmap network diff`."
        )
    lines.append("")

    return "\n".join(lines)
