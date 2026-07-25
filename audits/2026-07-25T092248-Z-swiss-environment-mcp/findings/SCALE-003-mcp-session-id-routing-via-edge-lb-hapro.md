## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-003` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Wie SCALE-002: In der aktuellen Single-Instance-Topologie existiert kein Edge-LB, den man konfigurieren könnte — alle vier Pass-Kriterien sind formal unerfüllt (fail). Der Server selbst ist mit der Mcp-Session-Id-Header-Exposition (CORS) LB-ready; die Routing-Konfiguration ist in docs/scaling.md als Pflicht beim ersten Scale-out festgehalten. [Lead-Auditor-Adjudikation 2026-07-25: fail->partial. Vorbedingung des Checks (horizontal skaliertes Deployment) ist nicht gegeben — render.yaml deployt eine Single-Instance, Affinitaet trivial erfuellt; docs/scaling.md dokumentiert die verbindlichen Muster fuer den Scale-out. Konsistent mit Juni-Audit bei identischem Katalog-Hash. Nicht pass, weil TTL/Failover ungetestet bleiben; wird zum harten fail, sobald >1 Replica deployt wird.]

Lücken im Detail:
- Kein Edge-LB mit Mcp-Session-Id-basiertem Routing (HAProxy stick-table / NGINX hash / Ingress-Annotation) konfiguriert.
- Keine Stick-Table-Kapazität und kein TTL definiert.
- Failover-Verhalten nicht getestet.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-003.md` (Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)).

### Evidence

- find/grep im Repo: keine haproxy.cfg, keine nginx.conf, keine ingress*.yaml, kein k8s/- oder helm/-Verzeichnis — kein Edge-LB liest den Mcp-Session-Id-Header
- src/swiss_environment_mcp/server.py:2649-2650 — CORS-Middleware erlaubt/exponiert den Mcp-Session-Id-Header (allow_headers/expose_headers); das ist nur die Client-seitige Voraussetzung, kein Routing
- docs/scaling.md:26-29 — Header-basiertes Stick-Table-Routing (Kapazität ≥100k, TTL ~24h) ist als Scale-out-Vorgabe dokumentiert, nicht konfiguriert
- render.yaml:1-17 — Render-managed LB ohne konfigurierbare Header-Affinität; kein Affinitäts- oder Failover-Test vorhanden

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Wie SCALE-002: Beim Scale-out Edge-LB mit Mcp-Session-Id-basiertem Routing (Stick-Table mit Kapazität + TTL) konfigurieren und Failover-Verhalten testen. Bis dahin dokumentierte Risiko-Akzeptanz der Single-Instance-Topologie.

### Effort Estimate

M
