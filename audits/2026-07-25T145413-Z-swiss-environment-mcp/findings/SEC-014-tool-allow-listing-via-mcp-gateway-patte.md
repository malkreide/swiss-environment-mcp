## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-014` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

applies_when nur via is_cloud_deployed==true erfuellt (enterprise/stadt_zuerich=false). Die Substanz des Checks (Lateral Movement zwischen Teams/Servern, rollenbasierter Zugriff) hat fuer einen single-server, no-auth, read-only Public-Data-Server praktisch keine Angriffsflaeche. Die harte technische Kontrolle (Allow-List/Gateway) bleibt jedoch unimplementiert. Ehrlich bewertet: Statuswechsel FAIL -> partial (accepted-risk) — begruendete, dokumentierte Risiko-Akzeptanz mit verbindlichen Re-Eval-Triggern + kompensierendem Snapshot-Gate rechtfertigt partial fuer dieses Profil, aber kein voller pass, da die Anforderung technisch offen bleibt.

Verbleibende Lücken:
- Harte Pass-Kriterien technisch unerfuellt: keine explizite default-deny Tool-Allow-List, kein Server-Side Group/Role-Check (mangels Auth/Gruppen nicht moeglich), keine team-/rollenspezifische tools/list-Filterung, keine Auditierung abgelehnter Tool-Calls.
- Kein vorgelagertes MCP-Gateway vorhanden.

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-014.md` (Tool-Allow-Listing via MCP-Gateway-Pattern).

### Evidence

- docs/security.md §'Tool-Allow-Listing / Gateway (SEC-014)' (Zeilen 62-74) formalisiert die Risiko-Akzeptanz: kein Auth-Modell, nur read-only Public-Data-Tools, tools/list fuer alle Clients identisch -> kein rollen-/teambasiertes Allow-Listing implementiert.
- Verbindliche Re-Evaluations-Trigger dokumentiert: Sobald (a) Auth-Modell, (b) write-faehige Tools oder (c) Enterprise-/Multi-Tenant-Kontext -> vorgelagertes MCP-Gateway mit Tool-Allow-List pro Rolle + 403-Auditierung zwingend (docs/security.md:70-74).
- Profilkontext stuetzt niedriges Risiko: enterprise_context=false, stadt_zuerich_context=false, write_capable=false, single-server, keine Fremd-Tools (profile.yaml).
- Kompensierend fuer Server-Integritaet: Tool-Definition-Snapshot tool-snapshot.json (SEC-022 CI-Gate), Namespace-Praefix env_ (README.md).

### Risk Description

Severity medium; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Für das aktuelle Profil (no-auth, read-only, Public Open Data, single-server, keine Fremd-Tools) technisch nicht umsetzbar; dokumentierte Risiko-Akzeptanz + kompensierendes Snapshot-Gate (SEC-022). Re-Evaluations-Trigger in docs/security.md: MCP-Gateway mit Tool-Allow-List pro Rolle + 403-Auditierung nachrüsten, sobald Auth/Write/Enterprise-Betrieb hinzukommt.

### Effort Estimate

M
