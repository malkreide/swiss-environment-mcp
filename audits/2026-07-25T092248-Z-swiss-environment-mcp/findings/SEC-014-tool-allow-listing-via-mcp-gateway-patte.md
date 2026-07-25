## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-014` (Check-Status: fail) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Kein Pflicht-Kriterium erfüllt: der cloud-deploybare Server steht ohne Gateway/Allow-Listing da. Das Risiko ist durch das Profil (read-only, Public Open Data, Snapshot-CI-Gate) gemindert und der Gateway-Bedarf für Enterprise-Kontexte ist dokumentiert — für den Check bleibt es dennoch ein fail.

Lücken im Detail:
- Keine Tool-Allow-List pro Team/Rolle dokumentiert oder konfiguriert (kein Gateway, kein default-deny im tools/list-Response)
- Keine Server-Side Defense-in-Depth via Group-/Role-Check — mangels Auth-Modell derzeit nicht umsetzbar
- Denied-Tool-Aufrufe werden nicht auditiert (kein 403-Pfad existiert)
- tools/list ist für alle Clients identisch, keine rollen-spezifische Filterung

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-014.md` (Tool-Allow-Listing via MCP-Gateway-Pattern).

### Evidence

- Repo-weite Suche (find/grep nach allowlist|tool-policy|gateway-config|allowed_tools) ohne Treffer — es existiert keine Team-/Rollen-Allow-List und kein Gateway-Config
- src/swiss_environment_mcp/server.py — keine Group-/Role-Checks (kein require_group, keine OAuth-Claims); Server hat kein Auth-Modell (docs/security.md: 'Auth: keine')
- docs/security.md (Abschnitt 'Tool-Poisoning / Gateway (SEC-015)') — dokumentierter Stand: Server läuft ohne vorgelagertes MCP-Gateway; für Enterprise-Einsatz wird Tool-Allow-Listing (default-deny) am Gateway explizit als nachzurüstende Massnahme benannt
- tool-snapshot.json + .github/workflows/ci.yml:40 (scripts/tool_snapshot.py check) — CI-Gate friert das Tool-Inventar ein (kompensierende Kontrolle gegen Tool-Drift, aber keine team-/rollenspezifische Filterung)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Für Enterprise-Einsatz ein MCP-Gateway mit Tool-Allow-List pro Rolle vorschalten (dokumentiert in docs/security.md). Für das aktuelle Profil (read-only, Public Open Data, kein Auth) bleibt der Verzicht eine dokumentierte Risiko-Akzeptanz; bei Einführung eines Auth-Modells zwingend neu bewerten.

### Effort Estimate

M
