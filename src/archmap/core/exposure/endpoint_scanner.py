from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from archmap.config import DEFAULT_MAX_FILE_SIZE_BYTES, ProjectConfig
from archmap.utils.file_utils import should_ignore_parts, to_file_id

# Extensions/filenames worth scanning for connection endpoints. Deliberately
# broader than the code-parsing file set (archmap.utils.file_utils.
# SUPPORTED_EXTENSIONS): connection config most often lives in .env files and
# plain config formats, not just source code, but source code (inline
# connection strings/env lookups) is included too.
_CONFIG_EXTENSIONS = {
    ".env", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties",
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".java", ".cs",
    ".php", ".rb", ".xml",
}

# URI schemes recognized as connection endpoints, mapped to the netscan
# service-name vocabulary (archmap.core.netscan.ports.WELL_KNOWN_SERVICES)
# so a match can be cross-referenced with scan results directly.
_SCHEME_TO_SERVICE: dict[str, str] = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "redis": "redis",
    "rediss": "redis",
    "mongodb": "mongodb",
    "amqp": "amqp",
    "amqps": "amqp",
    "mqtt": "mqtt",
    "mqtts": "mqtt",
    "ldap": "ldap",
    "ldaps": "ldaps",
    "ftp": "ftp",
    "ftps": "ftp",
    "sftp": "ssh",
    "ssh": "ssh",
    "smtp": "smtp",
    "smtps": "smtps",
    "memcached": "memcached",
}

_URI_PATTERN = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://(?:[^\s'\"/@]+@)?"
    r"(?P<host>[a-zA-Z0-9_.-]+):(?P<port>\d{2,5})"
)

_HOST_KEY_PATTERN = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9]*)_HOST\s*[:=]\s*[\"']?(?P<host>[a-zA-Z0-9_.-]+)[\"']?",
    re.IGNORECASE,
)
_PORT_KEY_PATTERN = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9]*)_PORT\s*[:=]\s*[\"']?(?P<port>\d{2,5})[\"']?",
    re.IGNORECASE,
)


class EndpointReference(TypedDict):
    file: str
    host: str
    port: int
    service: str | None


def scan_endpoint_references(
    project_root: str | Path,
    config: ProjectConfig | None = None,
) -> list[EndpointReference]:
    """Scan project files for literal host:port connection endpoints.

    Looks for two patterns: connection URIs with a known scheme
    (`redis://host:6379`, `postgres://user@host:5432/db`, ...) and paired
    `*_HOST`/`*_PORT` config keys sharing the same prefix (`DATABASE_HOST` /
    `DATABASE_PORT`). Regex-based and best-effort by design — a false
    negative here just means a correlation falls back to the lower-confidence
    service-name match; it never invents a finding on its own.
    """
    root = Path(project_root).resolve()
    if root.is_file():
        return _scan_file(root, root)

    ignore_dirs = config["analysis"]["ignore_dirs"] if config else []
    max_file_size_bytes = (
        config["analysis"].get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
        if config
        else DEFAULT_MAX_FILE_SIZE_BYTES
    )

    references: list[EndpointReference] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if not _is_scannable(file_path):
            continue
        parts = file_path.relative_to(root).parts
        if should_ignore_parts(parts, ignore_dirs):
            continue
        if max_file_size_bytes > 0:
            try:
                if file_path.stat().st_size > max_file_size_bytes:
                    continue
            except OSError:
                continue
        references.extend(_scan_file(file_path, root))

    return references


def _is_scannable(file_path: Path) -> bool:
    if file_path.suffix.lower() in _CONFIG_EXTENSIONS:
        return True
    return file_path.name.startswith(".env")


def _scan_file(file_path: Path, project_root: Path) -> list[EndpointReference]:
    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return []

    file_id = to_file_id(project_root, file_path)
    references: list[EndpointReference] = []

    for match in _URI_PATTERN.finditer(content):
        scheme = match.group("scheme").lower()
        service = _SCHEME_TO_SERVICE.get(scheme)
        if service is None:
            continue
        references.append(
            {
                "file": file_id,
                "host": match.group("host"),
                "port": int(match.group("port")),
                "service": service,
            }
        )

    hosts_by_prefix: dict[str, str] = {}
    for match in _HOST_KEY_PATTERN.finditer(content):
        hosts_by_prefix[match.group("prefix").upper()] = match.group("host")
    ports_by_prefix: dict[str, int] = {}
    for match in _PORT_KEY_PATTERN.finditer(content):
        ports_by_prefix[match.group("prefix").upper()] = int(match.group("port"))

    for prefix, host in hosts_by_prefix.items():
        port = ports_by_prefix.get(prefix)
        if port is None:
            continue
        references.append({"file": file_id, "host": host, "port": port, "service": None})

    return references
