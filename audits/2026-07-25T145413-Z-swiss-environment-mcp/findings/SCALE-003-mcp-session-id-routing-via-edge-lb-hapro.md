## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-003` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

Adjudiziert als dokumentierte Single-Instance-Risiko-Akzeptanz (accepted-risk). SCALE-003 ergaenzt SCALE-002 um den konkreten Routing-Layer und greift erst bei multi-instance-Deployment. Die verbindliche Edge-LB-Konfiguration (HAProxy Stick-Table auf Mcp-Session-Id, TTL >= 24h, Kapazitaet >= 100k) ist als Scale-out-Trigger in docs/scaling.md hinterlegt, aber im aktuellen Single-Instance-Betrieb nicht aktiv. Ehrliche Einordnung nach Pass-Kriterien: partial.

Verbleibende Lücken:
- Kein Edge-LB liest den Mcp-Session-Id-Header (keine HAProxy-Stick-Table / NGINX-Hash / K8s-Ingress-Affinity implementiert) — strenge Pass-Kriterien nicht erfuellt.
- Kein Affinitaets-/Failover-Runtime-Test (Modus 2), da kein Edge-LB im Single-Instance-Setup vorhanden.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-003.md` (Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)).

### Evidence

- docs/scaling.md:19-37 — Scale-out-Abschnitt beschreibt den konkreten Edge-LB-Routing-Layer: HAProxy/Nginx/K8s-Ingress routet anhand des Mcp-Session-Id-Headers konsistent auf dasselbe Backend; HAProxy-Stick-Table auf den Header, TTL korreliert mit Session-TTL (z.B. 24h), Kapazitaet >= 100k Sessions.
- docs/scaling.md:5-17 — Begruendung, warum aktuell kein Edge-LB-Routing noetig ist: Single-Instance-Topologie, alle Requests einer Mcp-Session-Id landen zwangslaeufig auf derselben Instanz.
- docs/scaling.md:33-37 — Failover-Regel dokumentiert: bei Backend-Ausfall darf eine Session ohne Shared State nicht stumm auf ein neues Backend umgeleitet werden (entweder Shared State oder sauberer Session-Neuaufbau).
- find . -name 'haproxy.cfg' -o -name 'nginx.conf' -o -name 'ingress*.yaml' -> keine Edge-LB-Konfiguration im Repo (konsistent mit Single-Instance).

### Risk Description

Severity high; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Wie SCALE-002: In der Single-Instance-Topologie existiert kein Edge-LB, den man auf Mcp-Session-Id-Routing konfigurieren könnte. Muster (Stick-Table mit Kapazität + TTL, Failover-Test) in docs/scaling.md festgehalten; verbindlich beim Scale-out.

### Effort Estimate

M
