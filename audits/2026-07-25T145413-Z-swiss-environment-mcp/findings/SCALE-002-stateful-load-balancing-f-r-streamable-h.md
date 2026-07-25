## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-002` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

Adjudiziert als dokumentierte Single-Instance-Risiko-Akzeptanz (accepted-risk). Die Pass-Kriterien des Checks setzen ein horizontal skaliertes Deployment voraus (applies_when transport==HTTP/SSE, multi-instance); die tatsaechliche Topologie ist bewusst single-instance, wodurch der Session-Stickiness-Bedarf strukturell entfaellt. docs/scaling.md haelt sowohl die aktuelle Entscheidung als auch die verbindlichen Muster + Re-Eval-Trigger fuer Scale-out fest. Ehrliche Einordnung nach Pass-Kriterien: partial (kein Sticky-LB/Shared-State implementiert), Risiko dokumentiert und begruendet.

Verbleibende Lücken:
- Keines der beiden Pass-Muster (Sticky Sessions ODER Shared-State-Session-Manager) ist implementiert — nach den strengen Pass-Kriterien nicht erfuellt.
- Kein Failover-Test (Modus 3), da in Single-Instance-Topologie kein Failover-Pfad existiert.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-002.md` (Stateful Load Balancing für Streamable HTTP / SSE).

### Evidence

- docs/scaling.md:5-17 — 'Aktueller Stand: Single-Instance': explizite Architektur-Entscheidung. Server laeuft als einzelne Instanz (Render Web Service / einzelner Container); alle Requests einer Mcp-Session-Id landen zwangslaeufig auf derselben Instanz -> kein verteiltes Session-Management noetig.
- docs/scaling.md:5-17 — State-Eigenschaften dokumentiert: keine serverseitig persistierten Sessions, jeder Tool-Call abgeschlossen/idempotent gegenueber oeffentlichen Daten, ein geteilter httpx.AsyncClient pro Prozess (Lifespan).
- docs/scaling.md:19-37 — Re-Evaluations-Trigger: Sobald horizontal skaliert wird, ist genau EINES der zwei Muster verbindlich: (1) Sticky Sessions am Edge-LB (SCALE-003) oder (2) Shared-State-Session-Manager (Redis / Durable Objects). Session-TTL in beiden Faellen explizit zu setzen; Failover ohne Shared State darf nicht stumm umgeleitet werden.
- Code-Review: kein redis/memcached/SessionStore/session_manager in src/ (grep negativ) — konsistent mit Single-Instance-Topologie (kein Shared State implementiert).

### Risk Description

Severity high; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Single-Instance-Topologie — Session-Affinität trivial erfüllt, verteiltes Session-Management nicht nötig. Dokumentiert in docs/scaling.md mit den verbindlichen Mustern (Sticky-LB / Shared-State) für den Scale-out. Wird zum harten Handlungsbedarf, sobald >1 Replica deployt wird.

### Effort Estimate

M
