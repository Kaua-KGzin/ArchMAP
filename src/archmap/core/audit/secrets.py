"""Offline secret detection shared by `archmap audit` and binary string analysis.

Detection is pattern-based and never contacts a provider to verify a key:
that keeps it usable offline (Termux, air-gapped CI) and side-effect free.
Each rule carries its own confidence, and matched values are always redacted
before they leave this module so a report can be shared safely.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TypedDict


class SecretRule(TypedDict):
    id: str
    name: str
    pattern: re.Pattern[str]
    severity: str
    confidence: float


class SecretMatch(TypedDict):
    rule: str
    name: str
    severity: str
    confidence: float
    redacted: str
    line: int


def _rule(rule_id: str, name: str, pattern: str, severity: str, confidence: float) -> SecretRule:
    return {
        "id": rule_id,
        "name": name,
        "pattern": re.compile(pattern),
        "severity": severity,
        "confidence": confidence,
    }


SECRET_RULES: list[SecretRule] = [
    _rule(
        "private-key",
        "Private key block",
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----",
        "critical",
        0.95,
    ),
    _rule(
        "aws-access-key",
        "AWS access key ID",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        "high",
        0.9,
    ),
    _rule(
        "github-token",
        "GitHub token",
        r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b",
        "high",
        0.95,
    ),
    _rule(
        "github-pat",
        "GitHub fine-grained token",
        r"\bgithub_pat_[A-Za-z0-9_]{60,255}\b",
        "high",
        0.95,
    ),
    _rule(
        "gitlab-token",
        "GitLab token",
        r"\bglpat-[A-Za-z0-9_\-]{20,}\b",
        "high",
        0.9,
    ),
    _rule(
        "slack-token",
        "Slack token",
        r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b",
        "high",
        0.9,
    ),
    _rule(
        "slack-webhook",
        "Slack webhook URL",
        r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}",
        "medium",
        0.9,
    ),
    _rule(
        "stripe-key",
        "Stripe secret key",
        r"\b[rs]k_live_[A-Za-z0-9]{20,}\b",
        "high",
        0.95,
    ),
    _rule(
        "google-api-key",
        "Google API key",
        r"\bAIza[0-9A-Za-z_\-]{35}\b",
        "medium",
        0.85,
    ),
    _rule(
        "anthropic-key",
        "Anthropic API key",
        r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b",
        "high",
        0.95,
    ),
    _rule(
        "openai-key",
        "OpenAI API key",
        r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}\b",
        "high",
        0.75,
    ),
    _rule(
        "jwt",
        "JSON Web Token",
        r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b",
        "medium",
        0.7,
    ),
    _rule(
        "url-credentials",
        "Credentials embedded in URL",
        r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]{3,}@[^\s/]+",
        "high",
        0.8,
    ),
]

# `password = "..."`-style assignments; the value must look like a real secret.
_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)
    \s*[:=]\s*
    ["']([^"'\s]{8,})["']
    """
)
_PLACEHOLDERS = re.compile(
    r"(?i)^(?:x+|\*+|changeme|change[_-]?me|example|dummy|test|password|secret|"
    r"your[_-].*|<.*>|\$\{.*\}|%\(.*\)s|\{\{.*\}\})$"
)


# Dev/CI defaults that appear in every `.env.example` and docker-compose file.
_PLACEHOLDER_PASSWORDS = frozenset({
    "pass", "password", "passwd", "pwd", "secret", "changeme", "change_me", "example",
    "test", "testing", "dummy", "user", "username", "postgres", "root", "admin",
    "guest", "mysql", "redis", "mongo", "sa", "dev", "local", "xxx", "placeholder",
})
_URL_CREDENTIALS = re.compile(r"://([^\s:/@]+):([^\s:/@]+)@([^\s/:?#]+)")


def _placeholder_url_credentials(url: str) -> bool:
    """``postgresql://user:password@localhost`` is a template, not a leak."""
    found = _URL_CREDENTIALS.search(url)
    if not found:
        return False
    password = found.group(2)
    if password.startswith(("$", "%", "<", "{")) or set(password) <= {"*", "x", "X"}:
        return True
    return password.casefold() in _PLACEHOLDER_PASSWORDS


def redact(value: str) -> str:
    """Keep just enough of a secret to recognise it: ``AKIA****WXYZ``."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * min(len(value) - 8, 16)}{value[-4:]}"


def string_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def scan_text(text: str, max_matches: int = 200) -> list[SecretMatch]:
    """Find secrets in ``text``; values are redacted in the result."""
    matches: list[SecretMatch] = []
    seen: set[tuple[str, int, str]] = set()

    def _line_of(index: int) -> int:
        return text.count("\n", 0, index) + 1

    for rule in SECRET_RULES:
        for found in rule["pattern"].finditer(text):
            value = found.group(0)
            key = (rule["id"], found.start(), value)
            if key in seen:
                continue
            if rule["id"] == "url-credentials" and _placeholder_url_credentials(value):
                continue
            seen.add(key)
            matches.append({
                "rule": rule["id"],
                "name": rule["name"],
                "severity": rule["severity"],
                "confidence": rule["confidence"],
                "redacted": redact(value),
                "line": _line_of(found.start()),
            })
            if len(matches) >= max_matches:
                return matches

    for found in _ASSIGNMENT.finditer(text):
        value = found.group(1)
        if _PLACEHOLDERS.match(value) or string_entropy(value) < 3.0:
            continue
        matches.append({
            "rule": "hardcoded-credential",
            "name": "Hardcoded credential assignment",
            "severity": "medium",
            "confidence": round(min(0.8, 0.4 + string_entropy(value) / 10), 2),
            "redacted": redact(value),
            "line": _line_of(found.start()),
        })
        if len(matches) >= max_matches:
            break
    return matches
