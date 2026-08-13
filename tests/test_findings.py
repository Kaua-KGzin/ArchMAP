"""Tests for unified findings model (core code findings)."""

from __future__ import annotations

from archmap.core.analyzer.findings import build_code_findings, max_severity


def test_max_severity() -> None:
    assert max_severity("info", "low") == "low"
    assert max_severity("low", "info") == "low"
    assert max_severity("medium", "high") == "high"
    assert max_severity("critical", "low") == "critical"
    assert max_severity("critical", "critical") == "critical"


def test_build_code_findings_from_empty() -> None:
    findings = build_code_findings([], {}, {})
    assert findings == []


def test_build_code_findings_circular_dependency() -> None:
    cycle_details = [
        {
            "members": ["src/a.py", "src/b.py", "src/c.py"],
            "path": ["src/a.py", "src/b.py", "src/c.py", "src/a.py"],
            "size": 3,
            "breakSuggestion": {
                "from": "src/c.py",
                "to": "src/a.py",
                "reason": "'src/a.py' has 2 incoming dependencies",
            },
        }
    ]
    findings = build_code_findings(cycle_details, {}, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding["id"] == "ARCH-001"
    assert finding["domain"] == "code"
    assert finding["category"] == "circular_dependency"
    assert finding["severity"] == "high"
    assert finding["confidence"] == 1.0
    assert "src/a.py" in finding["message"]
    assert len(finding["evidence"]) >= 1


def test_build_code_findings_god_module() -> None:
    risks = {
        "god_modules": [
            {"file": "src/core.py", "outgoing": 25},
            {"file": "src/util.py", "outgoing": 15},
        ],
        "layer_violations": [],
        "dependency_explosions": [],
        "top_risk_files": [],
        "thresholds": {"god_module_min_outgoing": 8, "dependency_explosion_min_connections": 12},
    }
    findings = build_code_findings([], risks, {})

    assert len(findings) == 2
    assert findings[0]["id"] == "ARCH-001"
    assert findings[0]["category"] == "god_module"
    assert findings[0]["file"] == "src/core.py"
    assert findings[0]["severity"] == "medium"
    assert "25" in findings[0]["message"]

    assert findings[1]["id"] == "ARCH-002"
    assert findings[1]["file"] == "src/util.py"


def test_build_code_findings_layer_violation() -> None:
    risks = {
        "god_modules": [],
        "layer_violations": [
            {
                "source": "src/api/handler.py",
                "target": "src/core/logic.py",
                "sourceLayer": "api",
                "targetLayer": "core",
                "rule": "api should not depend on core",
            }
        ],
        "dependency_explosions": [],
        "top_risk_files": [],
        "thresholds": {"god_module_min_outgoing": 8, "dependency_explosion_min_connections": 12},
    }
    findings = build_code_findings([], risks, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding["id"] == "ARCH-001"
    assert finding["category"] == "layer_violation"
    assert finding["severity"] == "medium"
    assert finding["source"] == "src/api/handler.py"
    assert finding["target"] == "src/core/logic.py"
    assert "api" in finding["message"]


def test_build_code_findings_dependency_explosion() -> None:
    risks = {
        "god_modules": [],
        "layer_violations": [],
        "dependency_explosions": [
            {
                "file": "src/config.py",
                "incoming": 22,
                "outgoing": 3,
                "totalConnections": 25,
            }
        ],
        "top_risk_files": [],
        "thresholds": {"god_module_min_outgoing": 8, "dependency_explosion_min_connections": 12},
    }
    findings = build_code_findings([], risks, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding["id"] == "ARCH-001"
    assert finding["category"] == "dependency_explosion"
    assert finding["severity"] == "low"
    assert finding["file"] == "src/config.py"
    assert "25" in finding["message"]


def test_build_code_findings_rule_violation() -> None:
    architecture = {
        "ruleViolations": [
            {
                "source": "src/controller.py",
                "target": "src/model.py",
                "kind": "forbid",
                "sourceTag": "controller",
                "targetTag": "model",
                "rule": "controller -> model",
                "message": "controller -> model is forbidden but src/controller.py depends on src/model.py",
            }
        ]
    }
    findings = build_code_findings([], {}, architecture)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["id"] == "ARCH-001"
    assert finding["category"] == "rule_violation"
    assert finding["severity"] == "high"
    assert finding["source"] == "src/controller.py"


def test_build_code_findings_all_types_deterministic_order() -> None:
    """Verify that IDs are assigned in deterministic order across categories."""
    cycle_details = [
        {
            "members": ["a.py", "b.py"],
            "path": ["a.py", "b.py", "a.py"],
            "size": 2,
            "breakSuggestion": None,
        }
    ]
    risks = {
        "god_modules": [{"file": "god.py", "outgoing": 20}],
        "layer_violations": [
            {
                "source": "s.py",
                "target": "t.py",
                "sourceLayer": "src",
                "targetLayer": "core",
                "rule": "test",
            }
        ],
        "dependency_explosions": [
            {"file": "exp.py", "incoming": 10, "outgoing": 10, "totalConnections": 20}
        ],
        "top_risk_files": [],
        "thresholds": {"god_module_min_outgoing": 8, "dependency_explosion_min_connections": 12},
    }
    architecture = {
        "ruleViolations": [
            {
                "source": "rs.py",
                "target": "rt.py",
                "kind": "forbid",
                "sourceTag": "r",
                "targetTag": "t",
                "rule": "r -> t",
                "message": "violation",
            }
        ]
    }

    findings = build_code_findings(cycle_details, risks, architecture)

    assert len(findings) == 5
    assert [f["id"] for f in findings] == ["ARCH-001", "ARCH-002", "ARCH-003", "ARCH-004", "ARCH-005"]
    assert findings[0]["category"] == "circular_dependency"
    assert findings[1]["category"] == "god_module"
    assert findings[2]["category"] == "layer_violation"
    assert findings[3]["category"] == "dependency_explosion"
    assert findings[4]["category"] == "rule_violation"


def test_build_code_findings_does_not_mutate_inputs() -> None:
    """Ensure the function never mutates input dicts."""
    original_cycle = {
        "members": ["a.py", "b.py"],
        "path": ["a.py", "b.py", "a.py"],
        "size": 2,
    }
    original_risks = {
        "god_modules": [{"file": "god.py", "outgoing": 20}],
        "layer_violations": [],
        "dependency_explosions": [],
        "top_risk_files": [],
        "thresholds": {"god_module_min_outgoing": 8, "dependency_explosion_min_connections": 12},
    }
    original_architecture = {"ruleViolations": []}

    cycle_copy = dict(original_cycle)
    risks_copy = {k: list(v) if isinstance(v, list) else v for k, v in original_risks.items()}
    arch_copy = {k: list(v) if isinstance(v, list) else v for k, v in original_architecture.items()}

    build_code_findings([original_cycle], original_risks, original_architecture)

    assert original_cycle == cycle_copy
    assert original_risks == risks_copy
    assert original_architecture == arch_copy
