# Security Policy

## Supported Versions

The table below lists which versions of ArchMAP currently receive security updates.

| Version       | Supported          |
| ------------- | ------------------ |
| 0.6.x (beta)  | ✅ Active development |
| 0.5.x         | ⚠️ Critical fixes only |
| < 0.5         | ❌ No longer supported |

> **Note:** ArchMAP is currently in pre-release (`v0.6.0-beta.0`). The API and behavior may
> still change. It is strongly recommended to always use the latest available version.

---

## Reporting a Vulnerability

If you discover a security vulnerability in ArchMAP, **please do not open a public issue.**

### How to report

Send a private report via one of the following channels:

- **GitHub Private Security Advisory** *(preferred)*:
  Go to [Security → Advisories](../../security/advisories/new) and click **"Report a vulnerability"**.
- **E-mail**: `kauagabrielxp@gmail.com`

Please include as much detail as possible:

- Description of the vulnerability and its potential impact
- Steps to reproduce (commands, input files, or code snippets)
- Affected version(s) and operating system
- Any suggestion for a fix, if applicable

### What to expect

| Step | Timeline |
|------|----------|
| Acknowledgment of receipt | Within **48 hours** |
| Initial assessment | Within **7 days** |
| Status update | Every **14 days** until resolved |
| Fix release (if confirmed) | As soon as possible; a patch release will be published |

### After the report

- **Accepted vulnerabilities** will result in a patch release and a public advisory crediting the reporter (unless anonymity is preferred).
- **Rejected reports** will receive a clear explanation of why the issue does not qualify as a security vulnerability.

---

## Scope

The following are considered **in scope**:

- Arbitrary code execution triggered by malicious input files
- Path traversal or directory escape during file parsing
- Denial of service caused by crafted source files (e.g., infinite loops in the parser)
- Unintended exposure of sensitive information in reports or exported files

The following are **out of scope**:

- Vulnerabilities in third-party dependencies (please report these upstream)
- Issues that require physical access to the machine running ArchMAP
- Theoretical risks without a demonstrable impact

---

## Security Best Practices

When using ArchMAP in automated pipelines (CI/CD), we recommend:

- Running ArchMAP in an isolated environment (container or sandbox)
- Avoiding analysis of untrusted codebases without prior inspection
- Keeping ArchMAP updated to the latest version

---

*This policy is inspired by the [GitHub coordinated disclosure model](https://docs.github.com/en/code-security/security-advisories).*
