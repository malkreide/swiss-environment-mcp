## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-007` (Check-Status: partial) |
| **PDF-Reference** | Sec 2.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Qualitativ sind die Tools atomar und gedanklich abgeschlossen — gerade der neue LINDAS-Code kapselt vorbildlich. Es fehlt aber durchgängig die Parallelisierung unabhängiger interner Calls (nirgends asyncio.gather), daher partial.

Lücken im Detail:
- Keine Parallelisierung interner Aggregationen: env_snow_current (2 unabhängige SLF-Calls) und env_bathing_water (Lizenz- und Site-Query beide nur vom cube_uri abhängig) könnten asyncio.gather nutzen — Pass-Kriterium 'wo Aggregation Sinn ergibt: gather' nicht erfüllt
- Aggregierter Charakter wird in den Descriptions nur teilweise explizit gemacht (z.B. env_snow_current erwähnt den internen 2-Quellen-Join nicht)

### Expected Behavior

Siehe Pass Criteria in `checks/ARCH-007.md` (Capability-Aggregation: Composability intern, Atomarität extern).

### Evidence

- src/swiss_environment_mcp/server.py:1510-1626 — env_bathing_water ist aus LLM-Sicht atomar: ein Call liefert Standort-Labels (nie rohe Code-URIs), Kantons-Join-Key, Probenwerte und Lizenzfeld; die 4-stufige SPARQL-Orchestrierung ist vollständig verkapselt (lindas/cube.py:316-376 löst Codes intern zu Labels auf)
- src/swiss_environment_mcp/server.py:2025-2058 — env_snow_current joint intern zwei SLF-API-Antworten (daily-snow + Stations-Metadaten) zu einem abgeschlossenen Resultat inkl. Sortierung
- src/swiss_environment_mcp/server.py:2327-2364 — env_hunting_stats liefert Jahres-Totale + Klassen direkt (kein Folge-Call nötig); Anchor-Demo-Query mit 1 Tool-Call beantwortbar
- src/swiss_environment_mcp/ — grep 'asyncio.gather' = 0 Treffer: unabhängige Sub-Calls laufen sequentiell (src/swiss_environment_mcp/server.py:2026-2027 snow+stations; src/swiss_environment_mcp/server.py:1517-1525 Lizenz+Sites nach Cube-Discovery)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Unabhängige interne Calls parallelisieren: env_bathing_water (Lizenz- + Site-Query) und env_snow_current (2 SLF-Calls) mit asyncio.gather. Aggregierten Charakter in den Tool-Descriptions erwähnen.

### Effort Estimate

S
