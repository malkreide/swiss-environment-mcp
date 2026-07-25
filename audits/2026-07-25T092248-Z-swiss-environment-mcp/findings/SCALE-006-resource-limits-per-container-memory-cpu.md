## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-006` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Memory-, CPU- und FD-Limits sowie restart-policy sind vollständig und korrekt dimensioniert konfiguriert — aber im Beispiel-Compose, nicht im produktiven Render-Pfad, und der geforderte OOM-Test fehlt. 4 von 5 Kriterien erfüllt → partial.

Lücken im Detail:
- OOM-Verhalten nicht getestet/dokumentiert (kein Stress-Test, kein docker-inspect-Nachweis OOMKilled/RestartPolicy).
- Explizite Limits existieren nur im als Beispiel deklarierten docker-compose.yml (Kommentar Zeile 1); im tatsächlichen Render-Deployment sind Memory/CPU nur über den Starter-Plan implizit gedeckelt.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-006.md` (Resource-Limits per Container (Memory, CPU, FDs)).

### Evidence

- docker-compose.yml:15-17 — mem_limit: 256m, mem_reservation: 128m, cpus: 0.5 (Reservation < Limit → Burst-Headroom vorhanden)
- docker-compose.yml:19-22 — ulimits nofile soft 4096 / hard 8192 (FD-Limit ≥ 4096 für viele ausgehende Connections)
- docker-compose.yml:23-29 — restart: unless-stopped plus Healthcheck gegen /health (Restart-Policy für OOM-Recovery aktiv)
- docs/scaling.md:39-43 — Resource-Limit-Strategie dokumentiert (Requests < Limits, ulimit -n ≥ 4096, restart-policy)
- render.yaml:5 — Produktiv-Deployment auf Render mit plan: starter; Limits dort nur implizit plattformseitig über den Plan, nicht als explizite Konfiguration im Repo

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Memory-/CPU-Limits aus dem Beispiel-Compose in den produktiven Render-Pfad übernehmen (render.yaml Plan-Limits dokumentieren) und einen kurzen OOM-/Restart-Verhaltenstest dokumentieren.

### Effort Estimate

S
