## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-002` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Alle drei Pass-Kriterien unerfüllt, daher fail trotz sauberer Risikodokumentation: docs/scaling.md begründet den Verzicht mit der Single-Instance-Topologie (Affinität trivial erfüllt) und benennt die verbindlichen Muster für den Scale-out. Das Finding wird akut, sobald mehr als eine Replica läuft. [Lead-Auditor-Adjudikation 2026-07-25: fail->partial. Vorbedingung des Checks (horizontal skaliertes Deployment) ist nicht gegeben — render.yaml deployt eine Single-Instance, Affinitaet trivial erfuellt; docs/scaling.md dokumentiert die verbindlichen Muster fuer den Scale-out. Konsistent mit Juni-Audit bei identischem Katalog-Hash. Nicht pass, weil TTL/Failover ungetestet bleiben; wird zum harten fail, sobald >1 Replica deployt wird.]

Lücken im Detail:
- Keines der beiden geforderten Muster (Sticky Sessions am Edge-LB / Shared-State-Session-Manager) ist implementiert.
- Keine explizite Session-Lifetime (TTL) definiert — FastMCP-Session-State lebt im Prozess-Memory.
- Kein Failover-Test vorhanden oder dokumentiert.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-002.md` (Stateful Load Balancing für Streamable HTTP / SSE).

### Evidence

- grep -rE 'redis|session_manager|SessionStore|stick|affinity|DurableObject' src/ *.yaml *.yml Dockerfile Procfile docs/ → keine Implementierung eines Sticky-Session- oder Shared-State-Musters (nur textuelle Erwähnung in docs/scaling.md)
- docs/scaling.md:5-16 — dokumentierter Ist-Zustand: Single-Instance (Render Web Service), keine serverseitig persistierten Sessions, kein verteiltes Session-Management
- docs/scaling.md:19-37 — Scale-out-Anforderungen (Sticky Sessions bzw. Redis-Shared-State, Session-TTL, Failover-Regel) sind als verbindliche Vorgabe beschrieben, aber nicht implementiert
- render.yaml:5 — plan: starter, keine Replica-/Scaling-Konfiguration; keine Session-TTL an irgendeiner Stelle gesetzt

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Single-Instance-Topologie ist dokumentiert (docs/scaling.md) — Finding wird verbindlich, sobald >1 Replica deployt wird: dann Sticky Sessions am Edge-LB oder externer Session-Store gemäss den in docs/scaling.md festgehaltenen Mustern, plus Failover-Test.

### Effort Estimate

M
