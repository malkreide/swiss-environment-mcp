# Security Policy & Posture

[🇩🇪 Deutsche Version](SECURITY.de.md)

`swiss-environment-mcp` was hardened against the internal MCP best-practice audit
catalogue. This document summarises the security posture and records the
**accepted-risk** decisions for controls that are deliberately handled at the
portfolio/gateway layer rather than inside this single server.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in `README.md`. Do not file public issues for exploitable
vulnerabilities.

## Posture summary

This is a **read-only**, **no-PII**, **public-open-data** MCP server. All 12
tools only query official Swiss federal environmental data sources (BAFU/SLF and
opendata.swiss). Hardening already in place:

| Area | Control |
|---|---|
| Egress | HTTPS-enforced allow-list to fixed BAFU/SLF/opendata.swiss hosts only (`ALLOWED_HOSTS` in `api_client.py`, SEC-021) |
| TLS | Verification on by default; DNS pinning closes the rebinding/TOCTOU window (SEC-005) |
| Binding | Network transports default to `127.0.0.1` (SEC-016) |
| Transport | Streamable HTTP with CORS exposing only `Mcp-Session-Id` (SDK-004) |
| Input | Pydantic v2 strict validation at all tool boundaries (SEC-018) |
| Secrets | None required — non-secret env-vars only, `.gitignore` guards `.env`, no hardcoded secrets (ARCH-005/SEC-013) |
| Errors | Upstream bodies logged to stderr, never forwarded to the model (OBS-002) |
| Stdout | Reserved for the JSON-RPC stream; logging pinned to stderr (OBS-004) |
| Tool integrity | Tool-definition snapshot (`tool-snapshot.json`) verified in CI against drift / rug-pulls (SEC-022) |

See [`docs/security.md`](docs/security.md) for the full security architecture
(data classification, lethal-trifecta assessment, secret management, session
model, egress control), `audits/` for the underlying audit reports, and
`CHANGELOG.md` for the hardening history.

## Accepted risks (portfolio-level controls)

The following audit checks are **not** implemented inside this server by design.
They are portfolio-wide concerns best enforced at an MCP gateway / host layer,
and the residual risk here is low because the server is read-only and only
reaches a fixed set of trusted public-data providers.

### SEC-014 — Tool allow-listing via an MCP gateway

**Status:** accepted risk (portfolio-level).
A per-tool allow-list belongs to the MCP host/gateway that aggregates multiple
servers, not to an individual server that exposes a fixed, read-only tool set.
If/when a central gateway is introduced for the portfolio, tool allow-listing
should be configured there. Until then, the risk is bounded: every tool is
read-only and constrained by the egress allow-list above.

### SEC-015 — Pre-flight tool-poisoning detection

**Status:** accepted risk (portfolio-level) — with a local guard in place.
Tool-poisoning (malicious tool descriptions / rug-pulls) is a supply-chain and
host-side concern. This server's tool definitions are version-controlled and
shipped from this repository; there is no dynamic/remote tool registration.
Locally, **SEC-022 tool-definition snapshotting** (`tool-snapshot.json`) detects
any drift in the tool surface in CI. Cross-server poisoning detection remains a
gateway/host responsibility tracked at the portfolio level.

## Re-evaluation triggers

These acceptances should be revisited if the server ever:

- gains **write** capability or starts processing **PII**, or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then implement SEC-014/015 there).
