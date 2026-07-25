## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-022` (Check-Status: partial) |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Hash-Pinning, CI-Gate und CHANGELOG-Disziplin sind vorhanden und für 0.3.0 nachweislich gepflegt; strikt gewertet fehlt aber der geforderte Re-Approval-Hinweis bei geänderten Tool-Definitionen, daher partial (5 von 6 Kriterien).

Lücken im Detail:
- Kein expliziter User-Re-Approval-Hinweis im CHANGELOG, obwohl 0.3.0 bestehende Tool-Definitionen geändert hat (BUG-01: env_flood_warnings/env_hydro_history) und der Snapshot-Hash damit wechselte
- Präfix 'env_' ist konsistent, trägt aber nicht die volle Server-Identität (z.B. 'swiss_environment__') — Rest-Kollisionsrisiko mit anderen Umwelt-/Environment-Servern

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-022.md` (Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull).

### Evidence

- Konsistentes env_-Namespace-Präfix über alle 18 Tools inkl. des neuen env_bathing_water (tool-snapshot.json:3-22; @mcp.tool(name=...) z.B. src/swiss_environment_mcp/server.py:809,1472)
- Tool-Definition-Hash-Snapshot regeneriert und aktuell: tool-snapshot.json mit tool_count=18 und sha256=3dd4498f... (tool-snapshot.json:2,24); Live-Check bestanden: 'python scripts/tool_snapshot.py check' → 'tool-snapshot OK (18 Tools, 3dd4498f540b)'
- Rug-Pull-Gate doppelt verankert: CI-Step (.github/workflows/ci.yml:40) und Test test_tool_snapshot_is_current (tests/test_unit.py:309-322)
- CHANGELOG nennt Tool-Definition-Änderungen explizit: 0.3.0 neues Tool env_bathing_water + 'Tool-Definitionen geändert → tool-snapshot.json neu erzeugt' (CHANGELOG.md:9-17,58-59); Versions-Bump 0.2.0→0.3.0 (pyproject.toml:7)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

CHANGELOG-Konvention ergänzen: bei geänderten Tool-Definitionen einen expliziten Re-Approval-Hinweis für Clients aufnehmen (Snapshot-Hash-Wechsel). Präfix-Frage (env_ vs. serverspezifischer) als bewusste Design-Entscheidung im README dokumentieren.

### Effort Estimate

S
