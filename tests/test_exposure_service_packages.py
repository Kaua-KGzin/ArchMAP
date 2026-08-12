from __future__ import annotations

from archmap.core.exposure.service_packages import (
    SERVICE_PACKAGE_HINTS,
    package_hints_for_service,
)


def test_package_hints_known_service() -> None:
    assert "redis" in package_hints_for_service("redis")


def test_package_hints_postgresql() -> None:
    hints = package_hints_for_service("postgresql")
    assert "psycopg2" in hints
    assert "asyncpg" in hints


def test_package_hints_unknown_service_returns_empty() -> None:
    assert package_hints_for_service("http-proxy") == []
    assert package_hints_for_service("totally-made-up") == []


def test_all_hint_lists_are_nonempty() -> None:
    for service, hints in SERVICE_PACKAGE_HINTS.items():
        assert hints, f"{service} has an empty hint list"
