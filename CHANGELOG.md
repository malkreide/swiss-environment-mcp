# Änderungsprotokoll / Changelog

Alle wesentlichen Änderungen werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]

## [0.4.1] – 2026-07-26

Wartungs-Release: Behebt die Upstream-Endpoint-Drift bei den Naturgefahren-/
Waldbrand-Tools (nicht breaking — Tool-Namen/-Parameter unverändert).
`env_wildfire_danger` liefert wieder echte Live-Gefahrenstufen; die
`naturgefahren.ch`-Tools sind zu deterministischen Routing-Tools umgebaut, weil
kein stabiler öffentlicher Warn-Feed mehr existiert (MeteoSchweiz-Probe
dokumentiert).

### Geändert / Changed

- **`env_hazard_overview` / `env_hazard_regions` → netzwerkfreie Routing-Tools
  (MeteoSchweiz-Follow-up):** Probe 2026-07-26
  ([`docs/probe-naturgefahren-hazards.md`](docs/probe-naturgefahren-hazards.md))
  bestätigt: Für die aggregierten Naturgefahren-/Wetterwarnungen existiert **kein
  stabiler, dokumentierter öffentlicher JSON-Feed** (MeteoSchweiz-OGD/STAC,
  opendata.swiss, App-API — alle geprüft). Statt eines fragilen Scrapings
  verweisen beide Tools jetzt **deterministisch** auf die dedizierten Live-Tools
  (Hochwasser→`env_flood_warnings`, Lawine→`env_avalanche_bulletin`,
  Waldbrand→`env_wildfire_danger`, Schnee→`env_snow_current`) und offizielle
  Portale; aggregierte Wetterwarnungen sind sauber an MeteoSchweiz/`meteoswiss-mcp`
  abgegrenzt. Kein toter Endpoint mehr.
- **Egress-Allow-List verkleinert (SEC-021):** `www.naturgefahren.ch` entfernt
  (kein HTTP-Call mehr) — aus `ALLOWED_HOSTS` und
  `deploy/network-policy.example.yaml`. Tote Fetcher `fetch_hazard_overview` /
  `fetch_regional_hazards` entfernt.

### Behoben / Fixed

- **`env_wildfire_danger` repariert (Upstream-Drift):** `waldbrandgefahr.ch`
  hat seinen REST-Endpoint `/api/danger` stillgelegt (404) und ist neu eine
  Rails/React-App. Der Client nutzt jetzt einen **zweistufigen Zugriff**
  (Startseite → `data-react-props`/`warnMapJsonPath` → signierte
  ActiveStorage-Blob-JSON) mit Schema-Guard; das Tool liefert wieder echte
  Gefahrenstufen je Region (Kanton-Mapping aus den react-props, höchste Stufen
  zuerst, ohne Filter auf 40 Regionen begrenzt).

### Bekannte Einschränkungen / Known findings

- **`naturgefahren.ch`-API stillgelegt:** Die Endpoints
  `/api/v1/warnings/overview/ch` und `/api/v1/warnings/regions` liefern
  301→404, ohne Drop-in-Ersatz. Konsequenz (in diesem Release umgesetzt):
  `env_hazard_overview` / `env_hazard_regions` sind zu netzwerkfreien
  Routing-Tools umgebaut (kein toter Endpoint, kein Scraping mehr) — siehe
  «Geändert». Aggregierte Wetterwarnungen bleiben bewusst an MeteoSchweiz/
  `meteoswiss-mcp` abgegrenzt.
- Funde in [`docs/probe-naturgefahren-waldbrand.md`](docs/probe-naturgefahren-waldbrand.md)
  und [`docs/probe-naturgefahren-hazards.md`](docs/probe-naturgefahren-hazards.md)
  dokumentiert; READMEs unter «Known Limitations» ergänzt.

### Tests

- Wildfire-Mocks auf den Zwei-Schritt-Vertrag umgestellt (Happy Path,
  Schema-Guard-Degradation, Fehlerpfad→`ToolError`). Mocked Suite 79 → 80.
- `tool-snapshot.json` regeneriert: die Tool-Descriptions von
  `env_hazard_overview` / `env_hazard_regions` / `env_wildfire_danger` wurden um
  die neuen Zugriffs-/Abkündigungs-Hinweise ergänzt (Description-Änderung,
  Namen/Parameter unverändert → nicht breaking für Clients).

## [0.4.0] – 2026-07-25

Erster getaggter Release seit v0.2.3 — bündelt die Hydro-Phase-2 (neues Tool
`env_bathing_water`, extraktionsfähiges `lindas/`-Modul; zuvor unter `[0.3.0]`
dokumentiert, aber nie getaggt) **und** die vollständige Audit-Remediation der
17 Findings des Re-Audits 2026-07-25.

**Auditbestätigt** (Re-Audit-Run `2026-07-25T145413-Z`, mcp-audit v1.0.0,
catalog `091f446b`): 44 anwendbare Checks → **38 pass / 6 partial / 0 fail**,
`production_ready: true`, keine blockierenden Fails. Die 6 verbleibenden partials
sind dokumentierte Risiko-Akzeptanzen bzw. ein begründeter Trade-off
(SEC-009/014/015, SCALE-002/003/004) mit Re-Evaluations-Triggern.

> **⚠️ Breaking (OBS-001):** Terminale Ausführungsfehler werden neu als
> `ToolError` geworfen → FastMCP setzt `isError:true`, statt den Fehlertext als
> erfolgreiches Resultat zurückzugeben. Recovery-Hinweise bleiben im
> Fehler-Content. Clients, die bisher Fehlertexte als normalen Output parsten,
> müssen `isError` auswerten. Details im Batch-1-Eintrag unten.

Die folgenden Batch-Einträge dokumentieren die Remediation im Detail; die
Hydro-Phase-2-Änderungen stehen unverändert im `[0.3.0]`-Block darunter.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 5: Deployment/Scale + Risiko-Akzeptanz

- **SCALE-004 — Image-Size-Gate:** neuer Workflow `.github/workflows/image-size.yml`
  baut das Runtime-Image und prüft die Grösse gegen ein Regressions-Ceiling
  (350 MB; das ≤200-MB-Ideal wird durch python-slim + otel-Extra knapp
  überschritten — das Gate fängt echte Regressionen). Läuft nur bei
  Image-relevanten Änderungen.
- **SCALE-006 — Resource-Limits im produktiven Pfad:** `render.yaml` dokumentiert
  die Plan-`starter`-Deckel (512 MB / 0.5 vCPU, Auto-Restart bei OOM);
  `docs/scaling.md` ergänzt eine Limits-Tabelle je Deployment-Pfad (Compose/
  Render/K8s) und ein reproduzierbares OOM-/Restart-Verfahren.
- **Risiko-Akzeptanz formalisiert (SEC-014, SEC-015, + Re-Evaluations-Trigger):**
  `docs/security.md` trennt Tool-Allow-Listing (SEC-014) und
  Tool-Poisoning-Detection (SEC-015), benennt die vier Detektions-Muster­klassen
  des Katalogs und die verbindlichen Trigger, ab wann die Kontrollen
  nachzurüsten sind (Auth-Einführung, write-Tools, Gateway-/Multi-Tenant-Betrieb).
  SCALE-002/003 (Sticky-LB/Shared-State) und SEC-009 (Session-Binding) bleiben
  dokumentierte Single-Instance-/No-Auth-Akzeptanzen in `docs/scaling.md` bzw.
  `docs/security.md`.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 4: Architektur-Politur

- **ARCH-007 — Parallelisierung unabhängiger interner Calls:**
  `env_bathing_water` holt Lizenz- und Standort-Query, `env_snow_current` die
  beiden SLF-Endpoints (Tageswerte + Stationen) neu via `asyncio.gather` statt
  sequenziell.
- **ARCH-012 — Protokollversion im Startup-Log:** die Lifespan loggt beim Start
  `server_start` mit `transport` und der vom SDK unterstützten
  `mcp_protocol_version` — ein SDK-Bump, der die Spec-Version verschiebt, wird
  damit im Audit-Trail sichtbar.
- **ARCH-006 — Tool-Budget-Begründung im README:** beide READMEs erklären, warum
  18 Tools über 6 Domänen (statt ≤12) use-case-getrieben sind und welche
  Konsolidierung (Stations-/Current-Paare) bewusst verworfen wurde.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 3: Security-Härtung

- **SEC-005 — eine DNS-Resolution pro Request:** `assert_host_allowed()` prüft
  nur noch Schema + Allow-List; die DNS-Auflösung samt IP-Blocklist erfolgt
  **einmalig** im `_PinnedTransport` unmittelbar vor dem Connect (zuvor lösten
  Guard *und* Transport je einmal auf → zwei `getaddrinfo`-Calls). Zwei neue
  Tests verifizieren: der Guard löst gar nicht mehr auf, der Transport genau
  einmal (Connect-Ziel = gepinnte IP).
- **SEC-021 — deploybares Network-Layer-Egress-Artefakt:**
  `deploy/network-policy.example.yaml` (vanilla `NetworkPolicy` + Cilium-FQDN-
  Egress auf exakt die Allow-List-Hosts). `docs/security.md` und CONTRIBUTING
  dokumentieren das verbindliche Verfahren für Allow-List-Erweiterungen
  (PR-Begründung, Manifest-Sync, CHANGELOG-Pflicht, Zweit-Review).
- **SEC-022 — Tool-Definitions-Governance dokumentiert:** CONTRIBUTING hält
  Snapshot-Regenerierung + expliziten Client-Re-Approval-Hinweis bei
  breaking Tool-Änderungen fest; das stabile `env_`-Präfix ist als bewusste
  Namespace-Entscheidung in beiden READMEs erklärt.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 2: Test-Coverage (OPS-001)

- **Gemockte Unit-Tests für die drei bisher ungetesteten Tools** (Happy Path +
  Fehlerpfad → `ToolError`): `env_hazard_overview`, `env_hazard_regions`,
  `env_wildfire_danger`. Damit hat jedes datenliefernde Tool CI-abgedeckte
  Erfolgs- und Fehlerpfade (6 neue Tests, Suite 71 → 77).
- **Eigenständige Live-Tests** für `env_snow_stations` und
  `env_avalanche_bulletin` (bisher nur indirekt über `test_slf_snow`).
- **`tests/test_20_scenarios.py`** ist nicht mehr ein pytest-unsichtbares
  Skript: neu als `live`-markierter `test_all_scenarios` sammelbar (aus der
  CI via `-m "not live"` ausgeschlossen), Docstring auf 18 Tools korrigiert,
  die Fehler-ID-Erwartung an die neue `isError`-Semantik (OBS-001) angepasst.

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
