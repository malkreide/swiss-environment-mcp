# Änderungsprotokoll / Changelog

Alle wesentlichen Änderungen werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]

### Neu (Audit-Remediation — verbleibende Findings)
- **OpenTelemetry-Tracing** (OBS-006, opt-in via `pip install '.[otel]'` +
  `OTEL_EXPORTER_OTLP_ENDPOINT`): pro Tool-Call ein Span `mcp.tool.<name>` mit
  `mcp.tool.name`/`mcp.tool.result.is_error`, httpx-Auto-Instrumentation, keine
  sensitiven Daten in Span-Attributen.
- **DNS-Pinning** für ausgehende Requests (SEC-005): Hostname wird einmalig
  aufgelöst, IP gegen Blocklist geprüft und das Connect-Ziel auf diese IP gepinnt
  (SNI/Cert weiterhin gegen den Hostnamen) — kein TOCTOU/DNS-Rebinding-Fenster.
- **JSON-Response-Envelope** zusätzlich für `env_bafu_datasets` und
  `env_flood_warnings` (SDK-002) — `response_format=json` liefert jetzt bei allen
  Such-/Listen-Tools den typisierten Envelope inkl. `match_type`.

### Geändert
- MCP-SDK auf Major-Version gepinnt (`mcp[cli]>=1.27,<2`) — legt die
  ausgehandelte Protokoll-Version deterministisch fest (ARCH-012).
- `docker-compose.yml` mit expliziten Memory/CPU/FD-Limits ergänzt (SCALE-006).

### Neu (Audit-Remediation)
- **CORS-Middleware für den HTTP-Transport** (SDK-004): `Mcp-Session-Id` wird via
  `expose_headers` für Browser-/SSE-Clients exponiert und in `allow_headers`
  zugelassen. Origins konfigurierbar über `MCP_CORS_ALLOW_ORIGINS` (Default `*`
  für Dev, in Produktion explizite Liste; Wildcard wird geloggt).

### Neu (Hardening / Dokumentation — Audit-Remediation Sprint 3)
- `docs/security.md`: Bedrohungsmodell, Lethal-Trifecta-Bewertung (SEC-019),
  Secret-Management (SEC-013), Session-Modell (SEC-009), Tool-Poisoning/Gateway
  (SEC-015), Egress-Kontrolle (SEC-021).
- `docs/scaling.md`: Single-Instance- und Scale-out-Strategie, Sticky-Sessions /
  Shared State (SCALE-002/003), Resource-Limits (SCALE-006).
- `docs/roadmap.md`: Phasenarchitektur (Phase 1 read-only) und Phasenübergänge (OPS-003).
- `.env.example` (nicht-geheime Konfig-Vorlage), `.github/dependabot.yml`
  (monatliche Updates, ARCH-012), `.github/workflows/security.yml`
  (gitleaks Secret-Scan, ARCH-005).
- README: Sektionen «MCP Protocol Version & Maintenance» (ARCH-012),
  «Lifecycle Phase» (OPS-003) und Begründung des Single-Modul-Layouts (ARCH-011);
  aktualisierter Projektstruktur-Baum (DE + EN).

## [0.2.0] – 2026-06-02

### Geändert
- **Tool-Definitionen geändert** (SEC-022, Tool-Snapshot aktualisiert): Alle 12
  Tool-Beschreibungen um `<use_case>`/`<important_notes>`-Tags ergänzt (ARCH-002).
- **JSON-Modus liefert neu einen typisierten Response-Envelope** mit Feldern
  `source`, `provenance`, `count`, `match_type`, `results`, `note` (SDK-002).
  Markdown bleibt das Default-Format. *Hinweis:* Wer den JSON-Output von
  `env_nabel_stations` / `env_hydro_stations` parst, muss auf die neuen
  Envelope-Keys umstellen.

### Neu
- Leere Such-/Listen-Resultate liefern `match_type: none` plus einen actionable
  Hinweis statt einer blanken Tabelle (ARCH-003).

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
