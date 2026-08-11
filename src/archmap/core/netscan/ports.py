from __future__ import annotations

# Service names for the ports scanned by default. Not exhaustive — good enough
# for a lightweight, no-dependency scanner running on a phone or a laptop.
WELL_KNOWN_SERVICES: dict[int, str] = {
    20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
    53: "dns", 67: "dhcp", 69: "tftp", 80: "http", 110: "pop3",
    111: "rpcbind", 123: "ntp", 135: "msrpc", 137: "netbios-ns",
    138: "netbios-dgm", 139: "netbios-ssn", 143: "imap", 161: "snmp",
    179: "bgp", 389: "ldap", 443: "https", 445: "microsoft-ds",
    465: "smtps", 514: "syslog", 515: "printer", 548: "afp",
    554: "rtsp", 587: "submission", 631: "ipp", 636: "ldaps",
    873: "rsync", 902: "vmware-auth", 993: "imaps", 995: "pop3s",
    1080: "socks", 1194: "openvpn", 1433: "ms-sql", 1521: "oracle",
    1723: "pptp", 1883: "mqtt", 2049: "nfs", 2181: "zookeeper",
    2222: "ssh-alt", 2375: "docker", 2376: "docker-tls", 3000: "dev-http",
    3128: "squid-proxy", 3306: "mysql", 3389: "rdp", 3690: "svn",
    4000: "dev-http-alt", 4444: "metasploit/msrpc", 5000: "dev-http-alt",
    5060: "sip", 5432: "postgresql", 5555: "adb", 5672: "amqp",
    5900: "vnc", 5985: "winrm-http", 5986: "winrm-https", 6379: "redis",
    6443: "kubernetes-api", 6666: "irc-alt", 6667: "irc", 7001: "weblogic",
    8000: "dev-http-alt", 8008: "http-alt", 8080: "http-proxy",
    8081: "http-alt", 8443: "https-alt", 8888: "http-alt", 9000: "dev-http-alt",
    9090: "prometheus", 9200: "elasticsearch", 9418: "git",
    11211: "memcached", 27017: "mongodb", 32400: "plex", 51820: "wireguard",
}

# Ordered roughly by real-world prevalence, similar in spirit to nmap's
# top-ports list. Used when the user asks for --top-ports N instead of an
# explicit --ports spec.
TOP_PORTS: list[int] = [
    80, 443, 22, 21, 23, 25, 3389, 8080, 445, 139, 135, 53, 110, 143,
    993, 995, 3306, 5432, 8443, 8000, 8888, 1723, 111, 199, 465, 587,
    631, 993, 1433, 1521, 2049, 2181, 27017, 6379, 6443, 8081, 9000,
    9090, 9200, 5900, 5985, 5986, 3000, 4000, 5000, 161, 179, 389,
    636, 873, 902, 1080, 1194, 1883, 2375, 2376, 2222, 3128, 5060,
    5555, 5672, 6667, 7001, 9418, 11211, 32400, 51820,
]


def service_name(port: int) -> str:
    return WELL_KNOWN_SERVICES.get(port, "unknown")


def parse_ports(spec: str | None, *, top: int | None = None) -> list[int]:
    """Parse a port spec like "22,80,443" or "1-1024" or "22,8000-8100".

    If `spec` is None, falls back to the top N most common ports
    (default 20, or `top` when given).
    """
    if not spec:
        count = top if top and top > 0 else 20
        ports = TOP_PORTS[:count]
        return sorted(set(ports))

    ports: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_str, _, end_str = chunk.partition("-")
            start, end = int(start_str), int(end_str)
            if start > end:
                start, end = end, start
            ports.update(range(start, end + 1))
        else:
            ports.add(int(chunk))

    invalid = [p for p in ports if p < 1 or p > 65535]
    if invalid:
        raise ValueError(f"invalid port(s): {sorted(invalid)}")

    return sorted(ports)
