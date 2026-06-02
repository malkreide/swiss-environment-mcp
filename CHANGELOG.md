# Änderungsprotokoll / Changelog

Alle wesentlichen Änderungen werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

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
