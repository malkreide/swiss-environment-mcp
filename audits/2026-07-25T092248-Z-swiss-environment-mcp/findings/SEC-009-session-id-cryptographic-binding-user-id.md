## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-009` (Check-Status: partial) |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Für einen auth-losen Public-Data-Server ist das Session-Risiko dokumentiert und materiell gering (nichts zu kapern: read-only, keine User-Daten). Die harten Pass-Kriterien (Binding, TTL, Invalidierung) sind aber nicht erfüllt — daher partial mit dokumentierter Risiko-Akzeptanz.

Lücken im Detail:
- Kein User-Binding (user_id:session_id) — mangels Auth-Modell nicht umsetzbar; die Kriterien 'Binding an validierten sub-Claim' und 'HTTP 401/403 bei Mismatch' sind unerfüllt (dokumentiert als bewusster Verzicht)
- Keine explizite Session-TTL und keine serverseitige Logout-Invalidierung konfiguriert
- Kryptografische Qualität der SDK-Session-IDs im Audit-Environment nicht direkt verifizierbar (mcp-Paket nicht installiert); Beleg stützt sich auf Delegation an das gepinnte SDK

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-009.md` (Session-ID Cryptographic Binding (user_id:session_id)).

### Evidence

- docs/security.md (Abschnitt 'Session-Modell (SEC-009)') — dokumentierter Entscheid: kein Auth-Modell, FastMCP verwaltet die Mcp-Session-Id; keine benutzerbezogenen Sessions, keine sensiblen Daten an Sessions gebunden; verbindliche Vorgaben (crypto IDs, sub-Binding, TTL, Logout-Invalidierung) für künftige OAuth-Einführung festgehalten
- src/swiss_environment_mcp/server.py:2634-2650 — build_cors_app expose_headers/allow_headers für Mcp-Session-Id, allow_credentials=False; Session-Handling vollständig an den MCP-SDK-Transport delegiert, kein eigener (potenziell schwacher) Session-Code im Repo
- pyproject.toml — mcp[cli]>=1.28.1,<2 gepinnt; die SDK-Session-ID-Generierung (uuid4) ist kryptografisch zufällig und wird nicht durch eigenen Code ersetzt
- docs/security.md (Datenklassifikation) — ausschliesslich Public Open Data, alle Tools read-only, keine Personendaten: Session-Hijacking hätte keinen Zugriff auf fremde Daten oder Schreib-Operationen zur Folge

### Risk Description

Severity critical gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Kein Auth-Modell → kein User-Session-Binding möglich; Entscheid ist in docs/security.md dokumentiert. Ergänzen: explizite Session-TTL-Empfehlung für den HTTP-Transport und Re-Evaluations-Trigger «sobald Auth eingeführt wird».

### Effort Estimate

S
