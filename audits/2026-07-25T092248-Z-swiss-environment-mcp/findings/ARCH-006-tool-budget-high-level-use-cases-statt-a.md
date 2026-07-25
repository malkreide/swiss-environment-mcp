## Finding: ARCH-006 — Tool-Budget: High-Level-Use-Cases statt API-Mapping 1:1

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-006` (Check-Status: partial) |
| **PDF-Reference** | Sec 2.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Substanziell gut: Use-Case-getriebene Tools, kein CRUD-/Endpoint-Mapping, Anchor-Query mit 1 Call, Budget in docs/ bewirtschaftet. Formal fehlt die geforderte Begründung im README selbst und die Anzahl liegt im Zweifelsband — daher partial statt pass.

Lücken im Detail:
- README enthält keine explizite Tool-Budget-Begründung, warum 18 Tools nötig sind bzw. keine weitere Aggregation möglich ist (Pass-Kriterium 'dokumentierte Begründung im README' — die Begründung liegt nur in docs/tool-inventory.md)
- 18 Tools überschreiten das Ideal (≤12) deutlich; Stations-/Current-Paare (nabel, hydro, snow) wären Kandidaten für Zusammenlegung oder Resources-Migration

### Expected Behavior

Siehe Pass Criteria in `checks/ARCH-006.md` (Tool-Budget: High-Level-Use-Cases statt API-Mapping 1:1).

### Evidence

- src/swiss_environment_mcp/server.py — 18 @mcp.tool-Registrierungen (grep-Count), in 6 thematischen Clustern (src/swiss_environment_mcp/server.py:5-13); liegt im Heuristik-Band 16-25 ('ernste Zweifel')
- docs/tool-inventory.md:58-62 — Tool-Budget explizit bewirtschaftet ('Stand jetzt 18 Tools in 6 Clustern (Budget 18 ausgeschöpft)') inkl. Zuständigkeitsmatrix/Abgrenzung zu meteoswiss-mcp (bewusster Verzicht auf Niederschlags-Tool)
- README.md:28 — Anchor-Demo-Query ('current air quality at NABEL station Zürich-Kaserne … WHO 2021') ist mit 1 Tool-Call (env_nabel_current) beantwortbar; Beispiel-Query-Tabelle README.md:191-203 mappt jede Frage auf genau 1 Tool
- src/swiss_environment_mcp/server.py:1510-1626 — kein 1:1-API-Mapping: NEU env_bathing_water aggregiert intern 4 SPARQL-Schritte (Cube-Version-Discovery, Lizenz, Dimension-Werte, Observations) hinter einem Tool; env_hunting_stats kapselt das undokumentierte Highcharts-Backend inkl. Total-Berechnung

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Tool-Budget-Begründung (warum 18 Tools, warum keine weitere Aggregation) vom docs/tool-inventory.md ins README spiegeln (2-3 Sätze). Mittelfristig prüfen, ob Stations-/Current-Paare zusammengelegt oder Stations-Listen zu MCP-Resources migriert werden können.

### Effort Estimate

S
