from __future__ import annotations

# Static, well-known risk notes for ports that are common targets or are
# frequently deployed without authentication. Not a vulnerability scanner —
# just enough signal to flag a port worth a second look in the report.
_PORT_RISKS: dict[int, tuple[str, str]] = {
    21: ("medium", "FTP often transmits credentials in plaintext"),
    23: ("high", "Telnet is unencrypted remote access"),
    69: ("medium", "TFTP has no authentication"),
    111: ("medium", "rpcbind can leak RPC service info to unauthenticated clients"),
    135: ("medium", "MSRPC endpoint mapper — common lateral-movement target"),
    139: ("medium", "NetBIOS session service — common lateral-movement target"),
    161: ("medium", "SNMP often uses default or weak community strings"),
    445: ("high", "SMB is a frequent target for exploits and lateral movement"),
    512: ("high", "rexec transmits credentials in plaintext"),
    513: ("high", "rlogin has no encryption or strong authentication"),
    514: ("high", "rsh has no encryption or strong authentication"),
    1433: ("medium", "MSSQL should not be reachable outside trusted networks"),
    1723: ("medium", "PPTP VPN uses broken encryption (MS-CHAPv2)"),
    2375: ("critical", "Unauthenticated Docker API allows remote code execution"),
    3306: ("medium", "MySQL should not be reachable outside trusted networks"),
    3389: ("high", "RDP is a frequent brute-force and exploit target"),
    5432: ("medium", "PostgreSQL should not be reachable outside trusted networks"),
    5900: ("high", "VNC is frequently run without authentication"),
    6379: ("high", "Redis is frequently deployed with no authentication"),
    8009: ("high", "AJP (Apache JServ Protocol) has had ghostcat-style file-read bugs"),
    9200: ("high", "Elasticsearch is frequently deployed with no authentication"),
    11211: ("high", "Memcached has no authentication and is abusable for DDoS amplification"),
    27017: ("high", "MongoDB is frequently deployed with no authentication"),
}

LEVEL_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def classify_port(port: int) -> dict[str, str] | None:
    risk = _PORT_RISKS.get(port)
    if risk is None:
        return None
    level, reason = risk
    return {"level": level, "reason": reason}
