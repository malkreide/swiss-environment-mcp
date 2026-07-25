## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-001` (Check-Status: partial) |
| **PDF-Reference** | Sec 6.1 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Kern-Trennung ist erreicht: Execution-Errors landen nie als JSON-RPC-Error, sondern in-band mit Recovery-Hinweisen, und beide Fehlerpfade sind getestet. Weil das isError-Flag bei Anwendungsfehlern nicht gesetzt wird und standardisierte Protocol-Fehlercodes nur implizit über das SDK kommen, bleibt es bei partial.

Lücken im Detail:
- Anwendungsfehler werden als regulärer String (Präfix 'Fehler:'/'⚠️') mit isError:false zurückgegeben statt mit gesetztem isError:true-Flag; die Fehlersignalisierung ist rein textuell (vgl. Heuristik _looks_like_error in src/swiss_environment_mcp/tracing.py:55-56).
- Keine standardisierten JSON-RPC-Fehlercode-Konstanten (-32601/-32602/-326xx) im eigenen Code; Protocol-Level-Errors sind vollständig ans MCP-SDK delegiert.

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-001.md` (Protocol vs. Execution Errors: korrekte Trennung).

### Evidence

- src/swiss_environment_mcp/server.py:79-101 — zentrale _handle_tool_error: alle 18 Tools fangen Anwendungsfehler (try/except, z.B. server.py:1627-1635 in env_bathing_water) und geben eine LLM-lesbare Meldung als reguläres Tool-Result zurück — nie als JSON-RPC-Error
- src/swiss_environment_mcp/api_client.py:226-252 — handle_http_error differenziert 404/429/503/Timeout/ConnectError/SecurityError/QueryError/QueryTimeoutError mit handlungsleitenden Meldungen (Recovery-Hinweise fürs LLM)
- tests/test_unit.py:250-270 — Execution-Error-Pfad getestet (HTTP 500 → maskiertes Result, ctx.warning, strukturiertes tool_error-Log)
- tests/test_unit.py:273-278 (plus 284-299) — Protocol-Error-Pfad getestet: ungültige Argumente → pydantic ValidationError
- Runtime-Test (Audit-Lauf): tools/call mit nicht existentem Tool → Tool-Result mit isError:true ('Unknown tool: nonexistent_tool'), Session bleibt intakt

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Anwendungsfehler mit isError:true signalisieren (FastMCP: Fehler-Result statt Fehler-String) unter Beibehaltung der Recovery-Hinweise im Content; Migration als Breaking Change für JSON-Konsumenten im CHANGELOG ankündigen.

### Effort Estimate

M
