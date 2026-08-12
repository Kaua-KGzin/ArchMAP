from __future__ import annotations

# Maps a netscan service name (archmap.core.netscan.ports.WELL_KNOWN_SERVICES
# vocabulary) to the common import/package root names a codebase would use
# to talk to that service, across ecosystems. Deliberately curated rather
# than exhaustive: prioritizes services that already carry a risk note in
# archmap.core.netscan.risk, plus a few common infra/dev services worth
# correlating even without a network-side risk rating.
SERVICE_PACKAGE_HINTS: dict[str, list[str]] = {
    "ftp": ["ftplib", "basic-ftp", "ftp"],
    "ssh": ["paramiko", "ssh2", "node-ssh", "fabric"],
    "smtp": ["smtplib", "nodemailer", "email"],
    "smtps": ["smtplib", "nodemailer"],
    "snmp": ["pysnmp", "net-snmp", "snmp-native"],
    "microsoft-ds": ["pysmb", "smbprotocol", "smb2"],
    "ms-sql": ["pyodbc", "pymssql", "mssql", "tedious"],
    "docker": ["docker", "dockerode", "docker-py"],
    "docker-tls": ["docker", "dockerode", "docker-py"],
    "mysql": ["mysql2", "pymysql", "mysqlclient", "mysql-connector-python", "mysql.connector"],
    "rdp": ["pyrdp", "node-rdpjs"],
    "postgresql": ["psycopg2", "psycopg", "pg", "asyncpg", "npgsql"],
    "vnc": ["vncdotool", "rfb", "node-vnc"],
    "kubernetes-api": ["kubernetes", "@kubernetes/client-node", "client-go"],
    "elasticsearch": ["elasticsearch", "@elastic/elasticsearch"],
    "memcached": ["pymemcache", "memcached", "python-memcached"],
    "mongodb": ["pymongo", "mongodb", "mongoose", "motor"],
    "redis": ["redis", "ioredis", "node-redis"],
    "amqp": ["pika", "amqplib", "amqp", "kombu"],
    "mqtt": ["paho-mqtt", "mqtt"],
    "zookeeper": ["kazoo", "node-zookeeper-client"],
    "oracle": ["cx_Oracle", "oracledb"],
    "prometheus": ["prometheus_client", "prom-client"],
    "openvpn": ["openvpn"],
    "ldap": ["ldap3", "python-ldap", "ldapjs"],
    "ldaps": ["ldap3", "python-ldap", "ldapjs"],
    "nfs": ["pynfs"],
    "rsync": ["rsync"],
}


def package_hints_for_service(service: str) -> list[str]:
    return SERVICE_PACKAGE_HINTS.get(service, [])
