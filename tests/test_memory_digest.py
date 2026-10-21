from __future__ import annotations

from archmap.core.memory import digest_changed, generate_memory_digest

_HEALTHY_REPORT = {
    "metrics": {"filesAnalyzed": 10, "totalDependencies": 25, "externalDependencies": 3},
    "risks": {
        "god_modules": [],
        "layer_violations": [],
        "dependency_explosions": [],
        "top_risk_files": [],
    },
    "cycles": [],
    "architecture": {
        "detectedStyle": {"name": "modular_monolith", "confidence": 0.8},
        "detectedLayers": ["core", "utils"],
        "ruleViolations": [],
        "health": {"score": 92, "grade": "A", "summary": "Looks great.", "drivers": []},
    },
}

_RISKY_REPORT = {
    "metrics": {"filesAnalyzed": 50, "totalDependencies": 200, "externalDependencies": 12},
    "risks": {
        "god_modules": [{"file": "src/core.py", "outgoing": 30}],
        "layer_violations": [
            {
                "source": "src/utils/x.py",
                "target": "src/cli/y.py",
                "sourceLayer": "utils",
                "targetLayer": "cli",
                "rule": "lower-level module should not depend on higher-level module",
            }
        ],
        "dependency_explosions": [],
        "top_risk_files": [
            {
                "file": "src/core.py",
                "riskScore": 70,
                "dependents": 12,
                "outgoing": 30,
                "signals": ["god_module"],
            }
        ],
    },
    "cycles": [["src/a.py", "src/b.py"]],
    "architecture": {
        "detectedStyle": {"name": "monolith", "confidence": 0.9},
        "detectedLayers": ["core"],
        "ruleViolations": [
            {
                "source": "src/ui/widget.py",
                "target": "src/db/client.py",
                "kind": "forbid",
                "message": "ui -> database is forbidden but src/ui/widget.py depends on ...",
            }
        ],
        "health": {
            "score": 40,
            "grade": "D",
            "summary": "Needs attention.",
            "drivers": ["1 circular dependency group(s)"],
        },
    },
}


def test_generate_memory_digest_includes_health_summary() -> None:
    text = generate_memory_digest(_HEALTHY_REPORT)

    assert "# ArchMAP Project Memory" in text
    assert "**92/100** (A)" in text
    assert "modular_monolith" in text
    assert "Files: 10" in text


def test_generate_memory_digest_omits_empty_sections() -> None:
    text = generate_memory_digest(_HEALTHY_REPORT)

    assert "## Top risk files" not in text
    assert "## Circular dependencies" not in text
    assert "## Layer violations" not in text
    assert "## God modules" not in text


def test_generate_memory_digest_includes_risk_sections_when_present() -> None:
    text = generate_memory_digest(_RISKY_REPORT)

    assert "## Top risk files" in text
    assert "src/core.py" in text
    assert "## Circular dependencies" in text
    assert "src/a.py → src/b.py" in text
    assert "## Layer violations" in text
    assert "## Custom architecture rule violations" in text
    assert "## God modules" in text


def test_generate_memory_digest_is_deterministic_besides_timestamp() -> None:
    first = generate_memory_digest(_RISKY_REPORT)
    second = generate_memory_digest(_RISKY_REPORT)

    assert not digest_changed(first, second)


def test_digest_changed_true_when_content_differs() -> None:
    healthy = generate_memory_digest(_HEALTHY_REPORT)
    risky = generate_memory_digest(_RISKY_REPORT)

    assert digest_changed(healthy, risky)


def test_digest_changed_true_when_no_existing_content() -> None:
    assert digest_changed(None, generate_memory_digest(_HEALTHY_REPORT))


def test_generate_memory_digest_caps_long_lists() -> None:
    many_god_modules = [{"file": f"src/f{i}.py", "outgoing": 20} for i in range(15)]
    report = {
        **_HEALTHY_REPORT,
        "risks": {**_HEALTHY_REPORT["risks"], "god_modules": many_god_modules},
    }

    text = generate_memory_digest(report)

    assert text.count("outgoing dependencies") == 10


# ---------------------------------------------------------------------------
# Network exposure section (v1.3.x)
# ---------------------------------------------------------------------------


def _snapshot(report, *, kind="expose", captured="2026-08-13T12:00:00Z"):
    return {
        "version": 1,
        "kind": kind,
        "target": str(report.get("target", "")),
        "capturedAt": captured,
        "report": report,
    }


def _finding(port, service, **overrides):
    finding = {
        "host": "192.168.1.10",
        "hostname": "db.local",
        "port": port,
        "protocol": "tcp",
        "service": service,
        "networkRisk": None,
        "severity": "info",
        "confidence": 0.0,
        "driftViolation": None,
    }
    finding.update(overrides)
    return finding


_DRIFT = {
    "source": "src/app.py",
    "target": "redis",
    "kind": "forbid",
    "rule": "app -> redis",
    "message": "app -> redis is forbidden but src/app.py depends on redis",
}

_EXPOSE_REPORT = {
    "target": "192.168.1.10",
    "findings": [
        _finding(
            6379,
            "redis",
            networkRisk={"level": "high", "reason": "no auth"},
            severity="high",
            confidence=0.95,
            driftViolation=_DRIFT,
        ),
        _finding(22, "ssh"),
    ],
    "driftViolations": [_DRIFT],
}


def test_digest_without_a_snapshot_is_unchanged() -> None:
    assert "## Network exposure" not in generate_memory_digest(_HEALTHY_REPORT)
    assert generate_memory_digest(_HEALTHY_REPORT) == generate_memory_digest(
        _HEALTHY_REPORT, None
    )


def test_digest_renders_the_network_section_from_a_snapshot() -> None:
    text = generate_memory_digest(_HEALTHY_REPORT, _snapshot(_EXPOSE_REPORT))

    assert "## Network exposure" in text
    assert "2026-08-13T12:00:00Z" in text
    assert "Open ports: 2 | Notable: 1 | Network rule violations: 1" in text
    assert "### Network rule violations" in text
    assert "app -> redis is forbidden" in text
    assert "`192.168.1.10:6379`" in text
    assert "confidence 95%" in text


def test_digest_network_section_filters_out_uninteresting_ports() -> None:
    text = generate_memory_digest(_HEALTHY_REPORT, _snapshot(_EXPOSE_REPORT))

    # port 22 is info severity, no risk, no confidence, no drift
    assert "192.168.1.10:22" not in text


def test_digest_network_section_works_from_a_bare_netscan_snapshot() -> None:
    netscan_report = {
        "target": "192.168.1.0/24",
        "hosts": [
            {
                "ip": "192.168.1.10",
                "hostname": None,
                "openPorts": [
                    {
                        "port": 6379,
                        "protocol": "tcp",
                        "service": "redis",
                        "risk": {"level": "high", "reason": "no auth"},
                    },
                    {"port": 8080, "protocol": "tcp", "service": "http", "risk": None},
                ],
            }
        ],
    }

    text = generate_memory_digest(_HEALTHY_REPORT, _snapshot(netscan_report, kind="netscan"))

    assert "`archmap netscan`" in text
    assert "port risk high" in text
    assert "### Network rule violations" not in text
    assert "192.168.1.10:8080" not in text


def test_digest_network_section_caps_long_lists() -> None:
    report = {
        "target": "10.0.0.0/24",
        "findings": [
            _finding(6000 + i, "redis", severity="high", host=f"10.0.0.{i}")
            for i in range(15)
        ],
        "driftViolations": [{**_DRIFT, "rule": f"rule-{i}"} for i in range(15)],
    }

    text = generate_memory_digest(_HEALTHY_REPORT, _snapshot(report))

    assert "...and 5 more" in text
    assert text.count("...and 5 more") == 2


def test_digest_network_section_is_deterministic() -> None:
    first = generate_memory_digest(_HEALTHY_REPORT, _snapshot(_EXPOSE_REPORT))
    second = generate_memory_digest(_HEALTHY_REPORT, _snapshot(_EXPOSE_REPORT))

    assert not digest_changed(first, second)
