# Security Policy

## Supported Versions

| Version   | Supported          |
| --------- | ------------------ |
| 0.6.x     | :white_check_mark: |
| < 0.6.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ArchMAP, please report it
responsibly.

**Do NOT open a public issue.**

Instead, please send a detailed report to the maintainer via:

- **GitHub Security Advisories:**
  [Report a vulnerability](https://github.com/Kaua-KGzin/ArchMAP/security/advisories/new)

Include the following in your report:

1. A description of the vulnerability and its potential impact.
2. Steps to reproduce the issue.
3. Any relevant logs, screenshots, or proof-of-concept code.
4. Your suggested fix, if you have one.

## Response Timeline

- **Acknowledgement:** within 48 hours.
- **Initial assessment:** within 7 days.
- **Fix release:** as soon as practical, typically within 30 days for
  confirmed vulnerabilities.

## Security Considerations

ArchMAP is a **local analysis tool**. The built-in HTTP server
(`archmap serve`) is designed for local use only and **must not** be
exposed to untrusted networks. If you need to serve the web UI
externally, place it behind an authenticated reverse proxy.

## Scope

The following areas are in scope for security reports:

- Path traversal in file-serving endpoints.
- Command injection via CLI arguments or API payloads.
- Denial of service through crafted input files or API requests.
- Dependency vulnerabilities in direct dependencies.

Out of scope:

- Issues that require physical access to the machine.
- Social engineering attacks.
- Vulnerabilities in third-party CDN resources loaded by the web UI
  (report these to the respective CDN providers).
