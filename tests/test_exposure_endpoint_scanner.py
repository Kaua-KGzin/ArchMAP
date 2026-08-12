from __future__ import annotations

from archmap.core.exposure.endpoint_scanner import scan_endpoint_references


def test_scan_finds_connection_uri(tmp_path) -> None:
    (tmp_path / "settings.py").write_text(
        'REDIS_URL = "redis://192.168.1.10:6379/0"\n', encoding="utf-8"
    )

    refs = scan_endpoint_references(tmp_path)

    assert len(refs) == 1
    assert refs[0]["host"] == "192.168.1.10"
    assert refs[0]["port"] == 6379
    assert refs[0]["service"] == "redis"
    assert refs[0]["file"] == "settings.py"


def test_scan_finds_paired_host_port_env_vars(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "DATABASE_HOST=192.168.1.50\nDATABASE_PORT=5432\n", encoding="utf-8"
    )

    refs = scan_endpoint_references(tmp_path)

    assert len(refs) == 1
    assert refs[0]["host"] == "192.168.1.50"
    assert refs[0]["port"] == 5432
    assert refs[0]["service"] is None
    assert refs[0]["file"] == ".env"


def test_scan_ignores_unrecognized_scheme(tmp_path) -> None:
    (tmp_path / "app.py").write_text('URL = "https://example.com:443/api"\n', encoding="utf-8")

    refs = scan_endpoint_references(tmp_path)

    assert refs == []


def test_scan_ignores_unscannable_extensions(tmp_path) -> None:
    (tmp_path / "image.png").write_bytes(b"redis://192.168.1.10:6379")

    refs = scan_endpoint_references(tmp_path)

    assert refs == []


def test_scan_respects_ignore_dirs(tmp_path) -> None:
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / ".env").write_text(
        "CACHE_HOST=10.0.0.1\nCACHE_PORT=6379\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text("API_HOST=10.0.0.2\nAPI_PORT=8080\n", encoding="utf-8")

    config = {"analysis": {"ignore_dirs": ["vendor"], "max_file_size_bytes": 0}}
    refs = scan_endpoint_references(tmp_path, config)

    assert len(refs) == 1
    assert refs[0]["host"] == "10.0.0.2"


def test_scan_finds_multiple_endpoints_in_one_file(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "DATABASE_HOST=192.168.1.50",
                "DATABASE_PORT=5432",
                "REDIS_HOST=192.168.1.51",
                "REDIS_PORT=6379",
            ]
        ),
        encoding="utf-8",
    )

    refs = scan_endpoint_references(tmp_path)

    hosts = {ref["host"] for ref in refs}
    assert hosts == {"192.168.1.50", "192.168.1.51"}


def test_scan_empty_project_returns_no_references(tmp_path) -> None:
    (tmp_path / "readme.txt").write_text("nothing to see here", encoding="utf-8")

    refs = scan_endpoint_references(tmp_path)

    assert refs == []
