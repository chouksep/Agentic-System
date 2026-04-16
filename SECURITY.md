# Security Policy

## Supported Versions

Only the latest version on the `main` branch is actively maintained and receives security fixes.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, open a [GitHub Security Advisory](https://github.com/chouksep/Agentic-System/security/advisories/new) (private, visible only to maintainers). Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Affected file(s) and line numbers if known

You can expect an acknowledgement within 72 hours and a resolution or mitigation plan within 14 days.

## Security Model

ci-wiki is a **local CLI tool** — it has no network-exposed endpoints, no authentication layer, and no multi-tenant isolation. The attack surface is limited to:

| Surface | Notes |
|---------|-------|
| URL ingestion (`--source <url>`) | Only ingest URLs from trusted sources. The fetcher blocks private/loopback/link-local/reserved IP ranges at DNS-resolution time to prevent SSRF. |
| Local file ingestion (`--source ./file.pdf`) | Files are read from the local filesystem. PDF size is capped at 50 MB to prevent OOM. |
| Databricks credentials | Read from `~/.databrickscfg` or environment variables. Never committed to git (enforced by `.gitignore`). |
| Wiki output | Stored as plain Markdown in `wiki/`. If the wiki contains sensitive competitive intelligence, keep the repository private. |
| SQLite database | `data/ci_wiki.db` is local and not exposed over the network. |

## Known Limitations

- **SSRF**: Mitigated by IP-range blocking at DNS resolution time, but no domain allowlist is enforced. Only ingest URLs from sources you trust.
- **PDF parsing**: Uses a regex-based extractor on raw bytes. Malformed or adversarial PDFs may produce garbled output but will not execute code.
- **No authentication**: This tool is designed for single-user local use. Do not run it in a shared or multi-user environment without additional access controls.

## Out of Scope

- Vulnerabilities in third-party dependencies (report directly to those projects)
- Theoretical attacks requiring physical access to the machine
- Denial-of-service via resource exhaustion from intentionally malformed inputs beyond the documented limits
