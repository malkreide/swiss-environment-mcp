## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-009` (Check-Status: partial) |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

applies_when erfuellt (transport != stdio-only, dual). Die harte Anforderung (Bindung an validierte User-Identitaet) bleibt technisch unerfuellt, weil kein Auth-/User-Konzept existiert; das zugrundeliegende Threat (Hijacking eines authentifizierten Opfer-Kontexts) hat mangels Auth und mangels privater Daten keine schaedliche Auspraegung. Dokumentierte, begruendete Risiko-Akzeptanz mit verbindlichen Re-Eval-Triggern. Ehrlich: partial (accepted-risk), unveraendert gegenueber Run 2026-07-25T092248-Z — die Remediation hat die Doku formalisiert, aber keine technische Kontrolle ergaenzt (weil bei no-auth nicht anwendbar).

Verbleibende Lücken:
- Harte Pass-Kriterien technisch unerfuellt: kein kryptografisches user_id:session_id-Binding, kein 401/403 bei Session-Mismatch, kein anwendungsseitiges TTL/Logout-Invalidation — mangels Auth nicht implementierbar.
- Session-ID-Generierung liegt im FastMCP-SDK (uuid4, crypto-sicher), aber ohne User-Binding und ohne Test-Nachweis im Repo.

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-009.md` (Session-ID Cryptographic Binding (user_id:session_id)).

### Evidence

- Kein Auth-Modell im Code (profile.yaml auth_model: none); kein anwendungsseitiges User-zu-Session-Binding, weil keine User-Identitaet existiert.
- docs/security.md §'Session-Modell (SEC-009)' (Zeilen 52-60) dokumentiert die bewusste Entscheidung: FastMCP verwaltet die Mcp-Session-Id selbst, keine benutzerbezogenen Sessions/sensitiven Daten an Sessions gebunden.
- Verbindliche Re-Evaluations-Trigger dokumentiert: bei kuenftiger OAuth/OIDC-Einfuehrung sind kryptografisch zufaellige Session-IDs, Bindung an validierten sub-Claim, explizite TTL und serverseitige Logout-Invalidierung vorgeschrieben (docs/security.md:58-60).
- Kompensierend: read-only, ausschliesslich Public Open Data — geleakte Session-ID hat keinen exfiltrierbaren Wert (docs/security.md §Datenklassifikation).

### Risk Description

Severity critical; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Kein Auth-Modell → ein User-zu-Session-Binding ist nicht anwendbar. Dokumentierte Risiko-Akzeptanz mit Re-Evaluations-Trigger in docs/security.md. Sobald OAuth/OIDC eingeführt wird: kryptografische Session-IDs, Bindung an validierten sub-Claim, explizite TTL, serverseitige Invalidierung.

### Effort Estimate

S
