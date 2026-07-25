## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-003` (Check-Status: partial) |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Fundament stimmt (structlog, JSON, stderr, gebundene Felder, keine prints), aber die Nutzung ist auf den Fehlerpfad mit einer einzigen Severity-Stufe beschränkt. Erfolgs-/Invocation-Logging mit Correlation-ID und weiteren Stufen fehlt → partial.

Lücken im Detail:
- Nur die Severity-Stufe 'warning' wird aktiv genutzt (server.py:89, server.py:2641) — gefordert sind mindestens 4 aktiv genutzte Stufen (debug/info/warning/error).
- Kein Log-Event pro Tool-Call (kein tool_invoked/tool_succeeded); Logging existiert nur im Fehlerpfad.
- Kein session_id/correlation_id im gebundenen Kontext — Multi-Step-Workflows sind nicht korrelierbar.

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-003.md` (Structured Logging mit RFC 5424 Severity-Stufen).

### Evidence

- pyproject.toml:28 — structlog>=24.1.0 in den Haupt-Dependencies
- src/swiss_environment_mcp/logging_setup.py:24-37 — JSONRenderer + ISO-TimeStamper + add_log_level + merge_contextvars; WriteLoggerFactory(file=sys.stderr)
- src/swiss_environment_mcp/server.py:72-73 — configure_logging() beim Modul-Import, Logger mit gebundenem Initial-Kontext (server=...)
- src/swiss_environment_mcp/server.py:89-95 — Fehlerpfad loggt strukturiert mit gebundenen Feldern (event tool_error, tool, error_type, detail, tool-spezifische Parameter); verifiziert in tests/test_unit.py:260-270 via capture_logs
- grep 'print(' src/ → 0 Treffer (keine print-Statements im Tool-Code)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Logging ausbauen: tool_invoked/tool_succeeded-Events (info), debug-Stufe für Upstream-Requests, error für unerwartete Ausfälle; request-/session-korrelierende ID in den gebundenen Logger-Kontext aufnehmen.

### Effort Estimate

M
