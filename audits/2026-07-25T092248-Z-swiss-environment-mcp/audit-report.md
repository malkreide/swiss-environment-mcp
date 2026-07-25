# MCP-Server Audit-Report — `swiss-environment-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-environment-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 27 bestanden, 17 Findings dokumentiert (1 critical, 8 high, 8 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-environment-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 2 | 0 | 3 | 0 | 0 |
| OPS | 2 | 0 | 1 | 0 | 0 |
| SCALE | 1 | 0 | 4 | 0 | 0 |
| SDK | 4 | 0 | 0 | 0 | 0 |
| SEC | 9 | 2 | 4 | 0 | 0 |
| **Total** | **27** | **2** | **15** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-009 | SEC | critical | partial |
| ARCH-006 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-007 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | partial |
| OBS-006 | OBS | medium | partial |
| SCALE-004 | SCALE | medium | partial |
| SCALE-006 | SCALE | medium | partial |
| SEC-014 | SEC | medium | fail |
| SEC-015 | SEC | medium | fail |

**Gesamt:** 17 Findings

---

## 5. Detail-Findings

### ARCH-006

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


### ARCH-007

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


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-012` (Check-Status: partial) |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

CHANGELOG-Disziplin, README-Policy-Sektion und Dependabot sind vorbildlich; das Kernkriterium — explizites protocolVersion-Pinning im Code statt SDK-Default — ist jedoch nicht erfüllt. 4 von 6 Kriterien erfüllt → partial.

Lücken im Detail:
- protocolVersion ist im Server-Code nicht explizit gepinnt — FastMCP wird ohne Versions-Pin instanziiert (server.py:310-322); der SDK-Major-Pin ist nur ein indirekter Proxy, ein Minor-Update des SDK kann die ausgehandelte Spec-Version still ändern
- CHANGELOG-Einträge nennen keine expliziten Spec-Version-Bumps (nur SDK-Pin-Erwähnung) — Audit-Trail-Lücke bei künftigen Protokollwechseln

### Expected Behavior

Siehe Pass Criteria in `checks/ARCH-012.md` (protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin).

### Evidence

- pyproject.toml:21-24 — SDK-Major-Pin 'mcp[cli]>=1.28.1,<2' mit explizitem ARCH-012-Kommentar ('legt die ausgehandelte MCP-Protokoll-Version fest'); aber KEIN explizites protocolVersion-Pinning im Server-Code (grep protocolVersion/protocol_version in src/ = 0 Treffer)
- CHANGELOG.md — vorhanden, Keep-a-Changelog-Format mit datierten Releases ([0.3.0] – 2026-07-25, Sektionen Neu/Architektur/Refactor/Behoben); CHANGELOG.md:167 dokumentiert den SDK-Pin
- README.md:295-304 — Sektion 'MCP Protocol Version & Maintenance' mit Update-Policy (Dependabot monatlich, semver-Bump bei Tool-/Verhaltensänderung, Tool-Snapshot-Gate SEC-022)
- .github/dependabot.yml — monatliche Update-PRs für pip UND github-actions aktiv

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Ausgehandelte protocolVersion beim Start loggen und im CHANGELOG bei SDK-Bumps den resultierenden Spec-Stand notieren; optional Pin über FastMCP-Konfiguration, sobald das SDK das erststellt.

### Effort Estimate

S


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-001` (Check-Status: partial) |
| **PDF-Reference** | Sec 6.1 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Kern-Trennung ist erreicht: Execution-Errors landen nie als JSON-RPC-Error, sondern in-band mit Recovery-Hinweisen, und beide Fehlerpfade sind getestet. Weil das isError-Flag bei Anwendungsfehlern nicht gesetzt wird und standardisierte Protocol-Fehlercodes nur implizit über das SDK kommen, bleibt es bei partial.

Lücken im Detail:
- Anwendungsfehler werden als regulärer String (Präfix 'Fehler:'/'⚠️') mit isError:false zurückgegeben statt mit gesetztem isError:true-Flag; die Fehlersignalisierung ist rein textuell (vgl. Heuristik _looks_like_error in src/swiss_environment_mcp/tracing.py:55-56).
- Keine standardisierten JSON-RPC-Fehlercode-Konstanten (-32601/-32602/-326xx) im eigenen Code; Protocol-Level-Errors sind vollständig ans MCP-SDK delegiert.

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-001.md` (Protocol vs. Execution Errors: korrekte Trennung).

### Evidence

- src/swiss_environment_mcp/server.py:79-101 — zentrale _handle_tool_error: alle 18 Tools fangen Anwendungsfehler (try/except, z.B. server.py:1627-1635 in env_bathing_water) und geben eine LLM-lesbare Meldung als reguläres Tool-Result zurück — nie als JSON-RPC-Error
- src/swiss_environment_mcp/api_client.py:226-252 — handle_http_error differenziert 404/429/503/Timeout/ConnectError/SecurityError/QueryError/QueryTimeoutError mit handlungsleitenden Meldungen (Recovery-Hinweise fürs LLM)
- tests/test_unit.py:250-270 — Execution-Error-Pfad getestet (HTTP 500 → maskiertes Result, ctx.warning, strukturiertes tool_error-Log)
- tests/test_unit.py:273-278 (plus 284-299) — Protocol-Error-Pfad getestet: ungültige Argumente → pydantic ValidationError
- Runtime-Test (Audit-Lauf): tools/call mit nicht existentem Tool → Tool-Result mit isError:true ('Unknown tool: nonexistent_tool'), Session bleibt intakt

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Anwendungsfehler mit isError:true signalisieren (FastMCP: Fehler-Result statt Fehler-String) unter Beibehaltung der Recovery-Hinweise im Content; Migration als Breaking Change für JSON-Konsumenten im CHANGELOG ankündigen.

### Effort Estimate

M


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-003` (Check-Status: partial) |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Fundament stimmt (structlog, JSON, stderr, gebundene Felder, keine prints), aber die Nutzung ist auf den Fehlerpfad mit einer einzigen Severity-Stufe beschränkt. Erfolgs-/Invocation-Logging mit Correlation-ID und weiteren Stufen fehlt → partial.

Lücken im Detail:
- Nur die Severity-Stufe 'warning' wird aktiv genutzt (server.py:89, server.py:2641) — gefordert sind mindestens 4 aktiv genutzte Stufen (debug/info/warning/error).
- Kein Log-Event pro Tool-Call (kein tool_invoked/tool_succeeded); Logging existiert nur im Fehlerpfad.
- Kein session_id/correlation_id im gebundenen Kontext — Multi-Step-Workflows sind nicht korrelierbar.

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-003.md` (Structured Logging mit RFC 5424 Severity-Stufen).

### Evidence

- pyproject.toml:28 — structlog>=24.1.0 in den Haupt-Dependencies
- src/swiss_environment_mcp/logging_setup.py:24-37 — JSONRenderer + ISO-TimeStamper + add_log_level + merge_contextvars; WriteLoggerFactory(file=sys.stderr)
- src/swiss_environment_mcp/server.py:72-73 — configure_logging() beim Modul-Import, Logger mit gebundenem Initial-Kontext (server=...)
- src/swiss_environment_mcp/server.py:89-95 — Fehlerpfad loggt strukturiert mit gebundenen Feldern (event tool_error, tool, error_type, detail, tool-spezifische Parameter); verifiziert in tests/test_unit.py:260-270 via capture_logs
- grep 'print(' src/ → 0 Treffer (keine print-Statements im Tool-Code)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Logging ausbauen: tool_invoked/tool_succeeded-Events (info), debug-Stufe für Upstream-Requests, error für unerwartete Ausfälle; request-/session-korrelierende ID in den gebundenen Logger-Kontext aufnehmen.

### Effort Estimate

M


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-006` (Check-Status: partial) |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Tracing-Implementierung selbst ist vollständig und sauber (Decorator auf allen 18 Tools, Auto-Instrumentation, PII-freie Spans, Env-basierte Konfiguration), aber sie ist im tatsächlichen Deployment nicht aktivierbar: das Docker-Image enthält das otel-Extra nicht und kein Manifest setzt den OTLP-Endpoint. Code-ready, deployment-inaktiv → partial.

Lücken im Detail:
- OTel-SDK ist nicht installiert im ausgelieferten Artefakt: Dockerfile:24 installiert das Wheel ohne [otel]-Extra — im Container bleibt configure_tracing selbst mit gesetztem OTLP-Endpoint ein stiller No-op (ImportError-Pfad tracing.py:39-40).
- Kein OTEL_EXPORTER_OTLP_ENDPOINT/OTEL_SERVICE_NAME in den Deployment-Manifesten (render.yaml, docker-compose.yml, Dockerfile) — Tracing ist im Cloud-Deployment faktisch inaktiv.
- Span-Attribut mcp.user.id fehlt (mangels Auth existiert keine User-Identity — nachvollziehbar, aber Kriterium formal unerfüllt).

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-006.md` (OpenTelemetry Distributed Tracing pro Tool-Call).

### Evidence

- src/swiss_environment_mcp/tracing.py:24-52 — configure_tracing: TracerProvider mit Resource (service.name via OTEL_SERVICE_NAME, deployment.environment via OTEL_ENVIRONMENT), BatchSpanProcessor + OTLP-HTTP-Exporter, Aktivierung nur bei gesetztem OTEL_EXPORTER_OTLP_ENDPOINT (Env-konfigurierbar, nichts hardcoded)
- src/swiss_environment_mcp/tracing.py:51 — HTTPXClientInstrumentor().instrument(): Backend-API-Calls (httpx) werden automatisch zu Child-Spans
- src/swiss_environment_mcp/tracing.py:59-78 — trace_tool-Decorator: Span 'mcp.tool.<name>' mit Attributen mcp.tool.name und mcp.tool.result.is_error; keine Args/Inhalte/Tokens in Span-Attributen (Docstring tracing.py:9-12, grep set_attribute → nur name/is_error)
- src/swiss_environment_mcp/server.py — @trace_tool auf allen 18 Tools (grep-Count 18/18, inkl. neuem env_bathing_water server.py:1481), aktiviert via configure_tracing() in server.py:76
- pyproject.toml:39-43 — otel-Extra (opentelemetry-sdk, otlp-proto-http-Exporter, instrumentation-httpx) als optionale Dependency

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Dockerfile auf 'pip install .[otel]' umstellen (oder otel-Extra ins Default-Set heben) und OTEL_EXPORTER_OTLP_ENDPOINT/OTEL_SERVICE_NAME als dokumentierte Env-Vars in render.yaml/docker-compose.yml aufnehmen — sonst bleibt Tracing im Cloud-Deployment faktisch inaktiv.

### Effort Estimate

S


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OPS-001` (Check-Status: partial) |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Test-Strategie (mocked/live-Trennung, Marker, CI-Exklusion, nightly Workflow) ist vollständig und der neue LINDAS-Code überdurchschnittlich getestet. Partial wegen der ungemockten Hazard-Tools und verfehlter Per-Tool-Quoten.

Lücken im Detail:
- Quantitatives Kriterium 'mind. 5 Unit-Tests pro Tool' verfehlt (72 gemockte Tests / 18 Tools ≈ 4): env_hazard_overview, env_hazard_regions und env_wildfire_danger haben KEINE gemockten Unit-Tests (nur Live-Tests) — Fehlerpfade dieser drei Tools sind in CI ungetestet
- Kein Live-Test für env_avalanche_bulletin und env_snow_stations als eigenständige Tools (nur indirekt via test_slf_snow)
- tests/test_20_scenarios.py ist ein Standalone-Skript ohne pytest-Testfunktionen (0 collected) und im Docstring veraltet ('Alle 12 Tools')

### Expected Behavior

Siehe Pass Criteria in `checks/OPS-001.md` (Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert).

### Evidence

- tests/test_unit.py (56 Tests) + tests/test_lindas.py (16 Tests) — respx-gemockte Unit-Tests inkl. Happy-/Error-/Edge-Pfaden; der NEUE lindas-Code ist gut abgedeckt (client 400/Timeout/Retry/POST, cube-Dedup/Label-Resolution/Injection-Guard, Bathing-Water happy/not-found/degradation tests/test_lindas.py:51-305)
- tests/test_integration.py:23 — 'pytestmark = pytest.mark.live': 16 Live-Tests decken fast alle Tools inkl. der neuen (test_bathing_water_lindas:177, test_slf_snow:202, test_hunting_stats:224)
- pyproject.toml [tool.pytest.ini_options] — live-Marker registriert ('live: Test trifft echte BAFU-Live-APIs …'); respx als dev-Dependency
- .github/workflows/ci.yml:44-48 — CI läuft 'pytest -m "not live"'; .github/workflows/live-tests.yml — separater nightly-Workflow (cron 0 4 * * *) + workflow_dispatch; Live-Tests brauchen keine Credentials (auth-freie Public-APIs, SEC-013 gegenstandslos)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Gemockte Unit-Tests für env_hazard_overview, env_hazard_regions, env_wildfire_danger ergänzen (Happy Path + Fehlerpfad), eigene Live-Tests für env_avalanche_bulletin/env_snow_stations, tests/test_20_scenarios.py als pytest-kompatibel refaktorieren oder als Skript deklarieren (Docstring '12 Tools' korrigieren).

### Effort Estimate

M


### SCALE-002

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


### SCALE-003

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


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-004` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Struktur ist vorbildlich: Multi-Stage mit benannten Stages, Slim-Base, Non-Root-User mit hoher UID, Healthcheck gegen den echten /health-Endpoint. Einzig das Grössen-Kriterium (<200 MB) konnte nicht bestätigt werden und ist gemäss Dependency-Footprint-Messung grenzwertig — daher partial statt pass.

Lücken im Detail:
- Final-Image-Grösse < 200 MB nicht verifizierbar (kein Docker-Daemon im Audit-Container); die Schätzung liegt mit ~210-220 MB unkomprimiert leicht über der Schwelle.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-004.md` (Containerization mit Multi-Stage-Builds).

### Evidence

- Dockerfile:2 und Dockerfile:15 — zwei FROM-Statements mit benannten Stages (AS builder / AS runtime); Build-Stage baut Wheel, Runtime-Stage installiert nur das Wheel (Dockerfile:23-24)
- Dockerfile:2,15 — beide Stages auf python:3.12-slim (Slim-Base)
- Dockerfile:20-21,34 — dedizierter Non-Root-User (uid/gid 10001, --no-create-home), USER app vor CMD
- Dockerfile:37-38 — HEALTHCHECK-Direktive (30s-Intervall) gegen /health; Endpoint existiert in src/swiss_environment_mcp/server.py:328-331 und liefert im Runtime-Test HTTP 200
- Grössen-Schätzung (Audit-Lauf, kein Docker-Daemon verfügbar): site-packages der installierten Dependencies = 92 MB + python:3.12-slim-Base ≈ 125 MB → ~210-220 MB unkomprimiert

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Image-Grösse in CI messen (docker build + docker image inspect als Workflow-Step mit Schwellwert-Gate <200 MB) oder Schwellwert-Abweichung dokumentieren; ggf. Dependencies im Runtime-Stage weiter beschneiden.

### Effort Estimate

S


### SCALE-006

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


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-005` (Check-Status: partial) |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

DNS-Pinning ist korrekt implementiert (Check und Connect atomar im Transport, SNI/Host erhalten) und greift auch für LINDAS über den geteilten Client. Partial, weil die Einmal-Resolution nur in der Substanz, nicht im Wortlaut erfüllt ist und der geforderte 1-DNS-Call-Test fehlt.

Lücken im Detail:
- Pass-Kriterium 'DNS-Resolution erfolgt einmalig' formal verfehlt: assert_host_allowed (api_client.py:154) und _PinnedTransport (Zeile 169) lösen je Request beide auf — zwei getaddrinfo-Calls; die Connect-IP stammt aber aus dem geprüften zweiten Lookup, daher kein ausnutzbares TOCTOU-Fenster
- Kein Test, der 'nur 1 DNS-Call pro Request' verifiziert (Pass-Kriterium); in den gemockten Suiten ist dns_pin_enabled sogar deaktiviert (tests/test_lindas.py:38-39, tests/test_unit.py:56-60), der Pinning-Pfad wird nicht end-to-end getestet

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-005.md` (DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU).

### Evidence

- src/swiss_environment_mcp/api_client.py:157-175 — _PinnedTransport löst auf, prüft die IP und setzt request.url.copy_with(host=ip): die geprüfte IP wird für den TCP-Connect verwendet
- src/swiss_environment_mcp/api_client.py:171-174 — sni_hostname-Extension trägt den Original-Hostnamen (TLS-SNI/Zertifikatsprüfung gegen Hostname, nicht IP); Host-Header bleibt der Original-Hostname (beim Request-Bau gesetzt, URL-Rewrite ändert ihn nicht)
- src/swiss_environment_mcp/api_client.py:183-193 — geteilter Client wird mit _PinnedTransport erzeugt; run_sparql (Zeile 271-278) nutzt get_client(), damit gilt das Pinning auch für den neuen LINDAS-Pfad (GET und POST in lindas/client.py laufen über diesen Client)
- tests/test_unit.py:193-215 — test_dns_pin_blocks_internal_ip (169.254.169.254 → SecurityError), test_dns_pin_returns_public_ip, test_client_uses_pinned_transport

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Doppelte DNS-Resolution (assert_host_allowed + _PinnedTransport) auf eine Resolution pro Request zusammenführen (Pin-Ergebnis durchreichen) und einen Unit-Test ergänzen, der genau einen getaddrinfo-Call pro Request verifiziert (Pinning-Pfad aktuell in beiden Suiten deaktiviert).

### Effort Estimate

S


### SEC-009

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


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-014` (Check-Status: fail) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Kein Pflicht-Kriterium erfüllt: der cloud-deploybare Server steht ohne Gateway/Allow-Listing da. Das Risiko ist durch das Profil (read-only, Public Open Data, Snapshot-CI-Gate) gemindert und der Gateway-Bedarf für Enterprise-Kontexte ist dokumentiert — für den Check bleibt es dennoch ein fail.

Lücken im Detail:
- Keine Tool-Allow-List pro Team/Rolle dokumentiert oder konfiguriert (kein Gateway, kein default-deny im tools/list-Response)
- Keine Server-Side Defense-in-Depth via Group-/Role-Check — mangels Auth-Modell derzeit nicht umsetzbar
- Denied-Tool-Aufrufe werden nicht auditiert (kein 403-Pfad existiert)
- tools/list ist für alle Clients identisch, keine rollen-spezifische Filterung

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-014.md` (Tool-Allow-Listing via MCP-Gateway-Pattern).

### Evidence

- Repo-weite Suche (find/grep nach allowlist|tool-policy|gateway-config|allowed_tools) ohne Treffer — es existiert keine Team-/Rollen-Allow-List und kein Gateway-Config
- src/swiss_environment_mcp/server.py — keine Group-/Role-Checks (kein require_group, keine OAuth-Claims); Server hat kein Auth-Modell (docs/security.md: 'Auth: keine')
- docs/security.md (Abschnitt 'Tool-Poisoning / Gateway (SEC-015)') — dokumentierter Stand: Server läuft ohne vorgelagertes MCP-Gateway; für Enterprise-Einsatz wird Tool-Allow-Listing (default-deny) am Gateway explizit als nachzurüstende Massnahme benannt
- tool-snapshot.json + .github/workflows/ci.yml:40 (scripts/tool_snapshot.py check) — CI-Gate friert das Tool-Inventar ein (kompensierende Kontrolle gegen Tool-Drift, aber keine team-/rollenspezifische Filterung)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Für Enterprise-Einsatz ein MCP-Gateway mit Tool-Allow-List pro Rolle vorschalten (dokumentiert in docs/security.md). Für das aktuelle Profil (read-only, Public Open Data, kein Auth) bleibt der Verzicht eine dokumentierte Risiko-Akzeptanz; bei Einführung eines Auth-Modells zwingend neu bewerten.

### Effort Estimate

M


### SEC-015

## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-015` (Check-Status: fail) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Pre-Flight-Tool-Poisoning-Detection ist nicht vorhanden — bewusst und in docs/security.md begründet (nur eigene Tool-Definitionen, Snapshot-CI-Gate als kompensierende Integritätskontrolle). Gegen die Pass-Kriterien gemessen (0/6) ergibt das ein fail; das Restrisiko ist beim aktuellen Single-Server-Profil gering.

Lücken im Detail:
- Kein Detection-Layer, keine der vier geforderten Pattern-Klassen (System-Prompts, Override-Phrasen, Invisible-Characters, Homoglyphs) abgedeckt
- Kein default-deny-Filter für high-risk Tool-Definitionen, kein Logging/SIEM-Alerting von Detection-Events
- Keine Tests für Standard-Angriffsmuster

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-015.md` (Pre-Flight Tool-Poisoning Detection).

### Evidence

- Repo-weite Suche (grep nach tool.poisoning|prompt.injection|sanitize.*description in src/ und deploy-Artefakten) ohne Treffer — kein Pre-Flight-Detection-Layer implementiert
- docs/security.md (Abschnitt 'Tool-Poisoning / Gateway (SEC-015)') — dokumentierte Risiko-Akzeptanz: eigenständiger read-only Public-Data-Server ohne Gateway, Detection 'für dieses Profil nicht erforderlich'; bei Enterprise-Einsatz Prompt-Injection-Filtering am Gateway gefordert
- tool-snapshot.json (Repo-Root) + .github/workflows/ci.yml:40 — Tool-Definition-Snapshot als CI-Gate (SEC-022) sichert die Integrität der eigenen Tool-Definitionen gegen unbemerkte Änderungen (Rug-Pull), ersetzt aber keine Pattern-Detection
- Keine Tests für Injection-/Homoglyph-/Zero-Width-Erkennung in tests/ (grep nach poisoning|injection|homoglyph ohne Treffer in Detection-Kontext)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Pre-Flight-Tool-Poisoning-Detection ist erst relevant, wenn fremde Tool-Definitionen aggregiert werden (Gateway-Szenario). Kompensierende Kontrolle heute: tool-snapshot.json + CI-Gate (SEC-022). Risiko-Akzeptanz in docs/security.md um die vier Pattern-Klassen des Checks ergänzen.

### Effort Estimate

M


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-021` (Check-Status: partial) |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Der Code-Layer ist vorbildlich und deckt auch die neuen LINDAS-/SLF-/Jagd-Hosts ab, aber der vom Check explizit verlangte zweite (Network-)Layer existiert nur als Prosa-Empfehlung; bei striktem Massstab 4 von 6 Pass-Kriterien erfüllt → partial trotz 4 gesammelter Evidenzpunkte.

Lücken im Detail:
- Network-Layer Egress Control ist nur als Empfehlung dokumentiert ('empfohlen für Cloud', docs/security.md:79-81) — kein deploybares Policy-Artefakt (keine NetworkPolicy/Security-Group in render.yaml, docker-compose.yml oder Dockerfile)
- Kein dokumentiertes Update-Verfahren für Allow-List-Erweiterungen (PR-Review + CHANGELOG-Pflicht) in docs/ oder CONTRIBUTING

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-021.md` (Egress-Allow-List: Code-Layer und Network-Layer).

### Evidence

- Code-Layer Allow-List als nicht-mutierbares frozenset mit 10 explizit benannten Gov-/SLF-Hosts (src/swiss_environment_mcp/api_client.py:82-97)
- Pre-Request-Check assert_host_allowed (HTTPS-Zwang + Host-Whitelist + IP-Blocklist) vor jedem ausgehenden Request: _get_json (api_client.py:217-221), _get_json_retry (api_client.py:524-538), LINDAS-Pfad via egress_check-Injection (api_client.py:271-278, lindas/client.py:113-114)
- Defense-in-Depth im Code: DNS-Pinning-Transport ohne TOCTOU-Fenster + Blocklist privater/loopback/link-local IPs (api_client.py:111-175), follow_redirects=False (api_client.py:192)
- Dokumentation der Egress-Policy inkl. DNS-Hinweis in docs/security.md:74-81; Allow-List-Hosts im Modul-Header benannt (api_client.py:11-15)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Network-Layer-Egress als deploybares Artefakt ergänzen (z.B. auskommentierte NetworkPolicy/egress-Rules in docker-compose.yml oder Render-Doku) und in CONTRIBUTING.md ein Update-Verfahren für ALLOWED_HOSTS-Erweiterungen (PR-Review + CHANGELOG-Pflicht) festschreiben.

### Effort Estimate

S


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-022` (Check-Status: partial) |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Hash-Pinning, CI-Gate und CHANGELOG-Disziplin sind vorhanden und für 0.3.0 nachweislich gepflegt; strikt gewertet fehlt aber der geforderte Re-Approval-Hinweis bei geänderten Tool-Definitionen, daher partial (5 von 6 Kriterien).

Lücken im Detail:
- Kein expliziter User-Re-Approval-Hinweis im CHANGELOG, obwohl 0.3.0 bestehende Tool-Definitionen geändert hat (BUG-01: env_flood_warnings/env_hydro_history) und der Snapshot-Hash damit wechselte
- Präfix 'env_' ist konsistent, trägt aber nicht die volle Server-Identität (z.B. 'swiss_environment__') — Rest-Kollisionsrisiko mit anderen Umwelt-/Environment-Servern

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-022.md` (Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull).

### Evidence

- Konsistentes env_-Namespace-Präfix über alle 18 Tools inkl. des neuen env_bathing_water (tool-snapshot.json:3-22; @mcp.tool(name=...) z.B. src/swiss_environment_mcp/server.py:809,1472)
- Tool-Definition-Hash-Snapshot regeneriert und aktuell: tool-snapshot.json mit tool_count=18 und sha256=3dd4498f... (tool-snapshot.json:2,24); Live-Check bestanden: 'python scripts/tool_snapshot.py check' → 'tool-snapshot OK (18 Tools, 3dd4498f540b)'
- Rug-Pull-Gate doppelt verankert: CI-Step (.github/workflows/ci.yml:40) und Test test_tool_snapshot_is_current (tests/test_unit.py:309-322)
- CHANGELOG nennt Tool-Definition-Änderungen explizit: 0.3.0 neues Tool env_bathing_water + 'Tool-Definitionen geändert → tool-snapshot.json neu erzeugt' (CHANGELOG.md:9-17,58-59); Versions-Bump 0.2.0→0.3.0 (pyproject.toml:7)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

CHANGELOG-Konvention ergänzen: bei geänderten Tool-Definitionen einen expliziten Re-Approval-Hinweis für Clients aufnehmen (Snapshot-Hash-Wechsel). Präfix-Frage (env_ vs. serverspezifischer) als bewusste Design-Entscheidung im README dokumentieren.

### Effort Estimate

S


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-009** (critical, partial)
2. **ARCH-006** (high, partial)
3. **OBS-001** (high, partial)
4. **OPS-001** (high, partial)
5. **SCALE-002** (high, partial)
6. **SCALE-003** (high, partial)
7. **SEC-005** (high, partial)
8. **SEC-021** (high, partial)
9. **SEC-022** (high, partial)
10. **ARCH-007** (medium, partial)
11. **ARCH-012** (medium, partial)
12. **OBS-003** (medium, partial)
13. **OBS-006** (medium, partial)
14. **SCALE-004** (medium, partial)
15. **SCALE-006** (medium, partial)
16. **SEC-014** (medium, fail)
17. **SEC-015** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| policy | `fail-or-partial` |


_Generated by tools/build_report.py — do not edit by hand._
