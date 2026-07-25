# Änderungsprotokoll / Changelog

Alle wesentlichen Änderungen werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 1: Observability

- **OBS-006 — Tracing im Deployment aktivierbar:** Das Docker-Image installiert
  neu das `[otel]`-Extra (`Dockerfile`); `render.yaml` setzt `OTEL_SERVICE_NAME`
  und exponiert `OTEL_EXPORTER_OTLP_ENDPOINT` (sync:false), `docker-compose.yml`
  dokumentiert beide. Tracing bleibt opt-in (No-op ohne Endpoint), ist jetzt aber
  ohne Rebuild einschaltbar.
- **OBS-003 — Logging über den Fehlerpfad hinaus:** `trace_tool` bindet je
  Tool-Call eine Correlation-ID (`request_id`) + `tool` in den Log-Kontext und
  emittiert `tool_invoked`/`tool_succeeded` (info) bzw. `tool_failed` (error).
  Ausgehende Upstream-Requests werden auf `debug` geloggt; `LOG_LEVEL` (Env)
  schaltet die Stufe um. Damit sind vier Severity-Stufen aktiv genutzt.

> **Breaking (OBS-001, JSON-/Protokoll-Konsument:innen):** Terminale
> Ausführungsfehler (Upstream nicht erreichbar, Egress blockiert) werden neu als
> `ToolError` geworfen — FastMCP setzt daraufhin `isError:true` im
> CallToolResult, statt den Fehlertext als *erfolgreiches* Resultat
> (`isError:false`) zurückzugeben. Die maskierte Meldung und die
> Direktzugang-Hinweise bleiben im Fehler-Content erhalten; Clients, die bisher
> den Fehlertext als normalen Output geparst haben, müssen neu `isError`
> auswerten. Graceful-Degradation-Pfade mit echten Ersatzdaten (z.B.
> Beispiel-Stationslisten in `env_hydro_stations`) und leere gültige Resultate
> (`match_type: none`, „keine aktive Warnung") bleiben unveränderte
> Erfolgs-Resultate.

## [0.3.0] – 2026-07-25

### Neu
- **`env_bathing_water` (18. Tool, Cluster Wasser):** Badegewässerqualität
  (E.coli/Enterokokken) aus dem LINDAS-Data-Cube `foen/ubd01041prod` — der
  einzige Hydro-Cube mit echter Mehrjahres-Zeitreihe (Saisondaten seit 2020).
  Standorte werden zu Labels aufgelöst (nie rohe Code-URIs), die Kantonsnummer
  aus der `containedInPlace`-URI wird als Join-Key mitgeliefert, jede Antwort
  trägt ein Lizenzfeld (ehrlicher Hinweis, wenn am Cube keine Lizenz deklariert
  ist — «im offenen Triplestore» ist nicht «frei verwendbar»).

### Architektur
- **Extraktionsfähiges `lindas/`-Modul (Drei-Schichten-Trennung):**
  `lindas/client.py` kennt nur SPARQL+HTTP (GET/POST je Query-Länge,
  45-s-Client-Timeout vor dem 60–90-s-Server-Abbruch, HTTP 400 als
  `QueryError` mit der MALFORMED-Meldung, Retry 2 s/4 s/8 s);
  `lindas/cube.py` kennt das cube.link-Vokabular (observationSet-Zwischenschritt,
  Versions-Deduplizierung über `schema:expires`, Code→Label-Auflösung,
  `pick_lang`, Lizenz-Suche auf Cube- und Graph-Ebene). Die Tools kennen nur
  `cube.py`. Das Modul wird nach `lindas-mcp` gehoben, sobald ein zweiter
  Server LINDAS nutzt.
- Der bestehende Hydro-LINDAS-Pfad (`run_sparql` und Fetcher) läuft neu über
  `lindas/client.py` (flache Result-Dicts statt roher Bindings).

### Known findings (aus der Live-Probe, docs/probe-lindas-hydro.md N1–N7)
- Direktzugriff `?cube cube:observation` liefert **0 Zeilen** ohne Fehler —
  der observationSet-Zwischenschritt ist zwingend.
- Abgelöste Cube-Versionen tragen `schema:expires`; das URI-Suffix kommt mal
  mit, mal ohne Trailing-Slash (`ubd0104/4/` vs. `ubd01041prod/13`).
- Lizenz liegt am Datensatz im Named Graph, nicht am Cube.

> **Breaking (nur interne API):** `api_client.run_sparql` liefert neu flache
> Dicts (Variable → Wert) statt roher SPARQL-Bindings; `api_client._binding_val`
> entfällt. Tool-Antworten sind nicht betroffen.

### Refactor
- **`sparql_client.py` als Portfolio-Baustein vereinheitlicht (Vendoring):** die
  Datei ist jetzt **byte-identisch** zur Kopie in `fedlex-mcp` (dortiger
  `_execute_sparql` bindet neu dünn daran). Ergänzt um einen optionalen
  `on_retry`-Callback (generisches Retry-Logging), rückwärtskompatibel. Der echte
  Single-Source-Schritt (`swiss-mcp-commons`-Paket) bleibt offen — siehe
  `docs/scaling.md`.
- **Wiederverwendbarer SPARQL-/JSON-Client extrahiert** (`sparql_client.py`):
  der aus `fedlex-mcp` stammende Retry-/Escape-/Binding-Aufbau ist jetzt ein
  abhängigkeitsarmes Modul (nur `httpx`/`asyncio`, Egress-Guard als Callback,
  HTTP-Client vom Aufrufer). `api_client.run_sparql` und `_get_json_retry` sind
  dünne Bindungen darauf; öffentliche Namen unverändert. So ist der Baustein 1:1
  in ein gemeinsames Portfolio-Paket hebbar (Cross-Repo-Paketierung als
  Folgeschritt, siehe `docs/scaling.md`).

### Behoben / Fixed
- **BUG-01 (historische Hydrodaten):** Die stillgelegten REST-Endpoints unter
  `hydrodaten.admin.ch/lhg/az/*` (Stunden-CSV, `warnings.json`, Stations-JSON,
  alle 404) werden nicht mehr aufgerufen. `env_flood_warnings` liest neu LINDAS
  `dangerLevel` (`fetch_hydro_warnings_lindas`); `env_hydro_history` liefert den
  aktuellsten LINDAS-Wert + den Bezugsweg für echte historische Reihen
  (BAFU-Abfragezentrale). Tote Fetcher `fetch_hydro_warnings` /
  `fetch_hydro_station_history` entfernt. (Tool-Definitionen geändert →
  `tool-snapshot.json` neu erzeugt.)

### Dokumentation
- **Jagdstatistik-Lizenz recherchiert (2026-07-19):** Daten BAFU-eigen (aus
  kantonalen Stellen; Technik Wildtier Schweiz), **nicht** als lizenzierter
  opendata.swiss-Datensatz publiziert, **keine explizite Lizenz** auf der Quelle.
  Attribution in jeder Antwort («Quellenangabe erforderlich»); formelle
  BAFU-Bestätigung bleibt offen. READMEs + `docs/probe-jagdstatistik.md` präzisiert.

### Neu / Added
- **Jagdstatistik-Tools** (Phase 3, Inkrement 3), Cluster «Jagd»:
  - `env_hunting_species` — 36 Tierarten mit sp-Codes (statisch eingebettet, lokal).
  - `env_hunting_stats` — Abschuss-/Fallwild-/Bestand-/Aussetzungszahlen je
    Tierart, Kanton und Jahr (2015–2024) aus dem `jagdstatistik.ch`-Backend.
  - **Architektur-Entscheid** (Abweichung von Dump-first): Live-Wrapper mit
    **eingebetteten statischen Lookups** (Tierart/Kanton/Datentyp) + **Schema-Guard**
    (Graceful Degradation), da der Container ephemer ist und kein persistenter Dump
    sinnvoll ist. Host `www.jagdstatistik.ch` in der Egress-Allow-List, AJAX-Header
    für den content-negotiierten JSON-Zugang. Tool-Anzahl 15 → 17.

### Known findings
- Jagdstatistik-Backend (`/de/statistics`) undokumentiert, Highcharts-zentriert:
  Datentyp-Param ist `th` (nicht `dt`), erst mit `th` greift der Kanton-Filter `ar`;
  Werte kommen als `[[v], …]` (verschachtelt). Lizenz auf der Quelle nicht
  ausgewiesen (BAFU-Terms anzunehmen, vor Release bestätigen).

- **SLF-Schnee- & Lawinen-Tools** (Phase 3, Inkrement 2), Cluster «Schnee/SLF»:
  - `env_snow_stations` — automatische IMIS-Schneemessstationen (Filter Kanton).
  - `env_snow_current` — aktuelle Schneehöhe (HS) & Neuschnee 24 h (HN_1D) in cm,
    je Station, mit Kanton-/Stations-Filter.
  - `env_avalanche_bulletin` — Lawinenwarnstufen (EAWS 1–5) je Warnregion aus dem
    CAAML-GeoJSON; ausserhalb der Saison sprechender «kein aktives Bulletin»-Pfad.
  - Datenquelle SLF-Datenservice (`measurement-api.slf.ch`, `aws.slf.ch`),
    **CC BY 4.0**, no-auth. Hosts in der Egress-Allow-List. Retry via
    `_get_json_retry`. Tool-Anzahl 12 → 15, `tool-snapshot.json` aktualisiert.
  - **Abgrenzung meteoswiss:** der SLF-IMIS-Niederschlagssensor (`RR_10MIN_SUM`)
    wird bewusst **nicht** als Tool angebunden (Zuständigkeitsmatrix).
- **LINDAS-SPARQL-Anbindung für Hydrodaten** (Phase 3). `env_hydro_current` und
  `env_hydro_stations` fragen primär den BAFU-LINDAS-Endpoint
  (`lindas.admin.ch/query`, Graph `foen/hydro`, `cube.link`-Data-Cube) ab und
  liefern typisierte Live-Werte (Pegel, Abfluss, Wassertemperatur,
  Gefahrenstufe) statt des fragilen `hydrodaten.admin.ch`-JSON-Scrapings. Der
  REST-Pfad bleibt als Fallback erhalten.
- SPARQL-Client (`run_sparql`, `sparql_escape`, `fetch_hydro_*_lindas`) mit
  Egress-Guard, Retry bei transienten Fehlern (429/502/503/504) und
  exponentiellem Backoff — Client-Aufbau bewusst aus `fedlex-mcp`
  wiederverwendet. `lindas.admin.ch` in die Egress-Allow-List aufgenommen.

### Known findings
- LINDAS `foen/hydro` enthält **nur aktuelle Werte** (eine Observation pro
  Station), keine historische Zeitreihe. `schema:identifier` ist `xsd:integer`
  → Stationsvergleich datentyp-robust über `STR(?id)`. Historische Längsschnitte
  weiterhin via `env_hydro_history` / opendata.swiss.

### Geändert / Changed
- Dokumentation an die einheitliche Portfolio-Struktur angeglichen: Root-Level
  `SECURITY.md` (Englisch) mit verlinkter `SECURITY.de.md` (Deutsch) ergänzt;
  README verweist nun auf die Security-Policy. LICENSE-Copyright auf
  «Hayal Oezkan» korrigiert.

## [0.2.0] – 2026-06-02

Erstveröffentlichung nach vollständiger Audit-Remediation (mcp-audit-skill):
31 Findings → 0, `production_ready: true`.

### Neu
- **CORS-Middleware** für den HTTP-Transport (SDK-004): `Mcp-Session-Id` via
  `expose_headers` für Browser-/SSE-Clients exponiert und in `allow_headers`
  zugelassen. Origins via `MCP_CORS_ALLOW_ORIGINS` konfigurierbar (Default `*`
  für Dev, in Produktion explizite Liste; Wildcard wird geloggt).
- **OpenTelemetry-Tracing** (OBS-006, opt-in via `pip install '.[otel]'` +
  `OTEL_EXPORTER_OTLP_ENDPOINT`): pro Tool-Call ein Span `mcp.tool.<name>` mit
  `mcp.tool.name`/`mcp.tool.result.is_error`, httpx-Auto-Instrumentation, keine
  sensitiven Daten in Span-Attributen.
- **Strukturiertes Logging** (OBS-003) via `structlog` nach **stderr** (JSON).
- **Typisierter JSON-Response-Envelope** (SDK-002) für alle Such-/Listen-Tools
  (`env_nabel_stations`, `env_hydro_stations`, `env_bafu_datasets`,
  `env_flood_warnings`): `source`, `provenance`, `count`, `match_type`,
  `results`, `note`. Markdown bleibt Default-Format.
- Leere Such-/Listen-Resultate liefern `match_type: none` + actionable Hinweis
  statt blanker Tabelle (ARCH-003).
- `<use_case>`/`<important_notes>`-Tags in allen 12 Tool-Beschreibungen (ARCH-002).
- `/health`-Endpoint für Cloud-Load-Balancer (SCALE-004/SEC-016).
- Gemockte Unit-Tests (respx) getrennt von Live-Tests (`live`-Marker); CI läuft
  `pytest -m "not live"`, nightly Live-Workflow (OPS-001).
- Tool-Definition-Snapshot + CI-Gate gegen «Rug Pull» (SEC-022).
- Docs: `docs/security.md` (Trifecta-Bewertung SEC-019, Secret-Mgmt SEC-013,
  Session-Modell SEC-009, Egress SEC-021), `docs/scaling.md` (SCALE-002/003/006),
  `docs/roadmap.md` (Phasenarchitektur OPS-003).
- `.env.example`, `.github/dependabot.yml` (ARCH-012),
  `.github/workflows/security.yml` (gitleaks, ARCH-005), `docker-compose.yml`
  mit expliziten Resource-Limits (SCALE-006).

### Geändert
- **Tool-Definitionen geändert** (SEC-022, Tool-Snapshot aktualisiert).
- Korrekter Cloud-Transport `streamable-http` (vorher ungültiges
  `streamable_http`) + behobenes Host-Binding (`MCP_HOST`, SEC-016) — macht das
  Cloud-Deployment erstmals lauffähig.
- Geteilter `httpx.AsyncClient` via FastMCP-Lifespan statt pro Tool-Call (SDK-001).
- Pydantic-Settings + transport-agnostische Server-Logik (ARCH-004).
- `ctx: Context` an allen Tools für Logging/Fehler über den MCP-Context (SDK-003).
- MCP-SDK auf Major-Version gepinnt (`mcp[cli]>=1.27,<2`, ARCH-012).
- Multi-Stage-Dockerfile, non-root User, HEALTHCHECK (SEC-007/SCALE-004).

### Sicherheit
- **SSRF-Härtung** (SEC-004): Egress-Allow-List (frozenset) + `assert_host_allowed`,
  HTTPS-Zwang, IP-Blocklist, `follow_redirects=False`.
- **DNS-Pinning** (SEC-005): Host einmalig auflösen, IP gegen Blocklist prüfen,
  Connect auf gepinnte IP (SNI/Cert gegen Hostnamen) — kein TOCTOU-Fenster.
- **Input-Whitelisting** (SEC-018): Regex-Pattern + `strict` auf Identifier-Inputs.
- **Fehler-Maskierung** (OBS-002): keine internen Details ans LLM; Detail nur im
  Server-Log.

> **Breaking (JSON-Konsument:innen):** Der JSON-Output von `env_nabel_stations` /
> `env_hydro_stations` nutzt neu die Envelope-Keys (`results`/`count`/… statt
> `nabel_stationen`/`total`). Markdown-Konsument:innen sind nicht betroffen.

## [0.1.0] – 2026-03-12

### Neu
- **12 Tools** in 4 thematischen Clustern
- **Luft (3):** `env_nabel_stations`, `env_nabel_current`, `env_air_limits_check`
- **Wasser (4):** `env_hydro_stations`, `env_hydro_current`, `env_hydro_history`, `env_flood_warnings`
- **Naturgefahren (3):** `env_hazard_overview`, `env_hazard_regions`, `env_wildfire_danger`
- **Umweltdaten (2):** `env_bafu_datasets`, `env_bafu_dataset_detail`
- **3 MCP-Resources:** Grenzwerte Luft, NABEL-Stationen, Hochwasser-Gefahrenstufen
- Schweizer LRV-Grenzwerte und WHO 2021-Richtwerte eingebaut
- Fallback-Antworten mit Direktlinks bei API-Ausfällen
- Duale Transport-Unterstützung: stdio (lokal) und Streamable HTTP (Cloud)
- GitHub Actions CI für Python 3.11–3.13
- Bilinguales README (DE/EN)

### Quellen
- hydrodaten.admin.ch (BAFU Hydrologie)
- naturgefahren.ch (SLF/BAFU)
- waldbrandgefahr.ch (BAFU)
- opendata.swiss CKAN-API (BAFU-Datenkatalog)
