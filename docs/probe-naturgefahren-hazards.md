# Live-Probe — MeteoSchweiz-Follow-up für die Naturgefahren-Tools

**Datum:** 2026-07-26
**Anlass:** Follow-up aus [`probe-naturgefahren-waldbrand.md`](probe-naturgefahren-waldbrand.md):
Die aggregierte `naturgefahren.ch`-Warnungs-API ist stillgelegt. Diese Probe
klärt, ob ein sauberer MeteoSchweiz-/OGD-Ersatz für `env_hazard_overview` /
`env_hazard_regions` existiert.

## Geprüfte Quellen (alle negativ für einen sauberen JSON-Feed)

| Quelle | Geprüft | Ergebnis |
|---|---|---|
| MeteoSchweiz-App-API (`app-prod-ws.meteoswiss-app.ch/v1/*`) | `warnings.json`, `warnings_with_outlook.json`, `plzDetail`, `warningsWithOutlook` … | alle **404** (Spring-Service, valide Pfade undokumentiert) |
| geo.admin STAC (`data.geo.admin.ch/api/stac`) | Collection-Liste (100), direkte IDs `ch.meteoschweiz.warnungen-*` | **keine** Warnungen-Collection; nur geospatiale Layer (GeoTIFF/GeoJSON, schwergewichtig). Einziger Treffer: `ch.bafu.gefahren-waldbrand_warnung` (Waldbrand — bereits abgedeckt) |
| opendata.swiss / CKAN | `q=Warnungen` + Org-Filter MeteoSchweiz | 1 Datensatz (Partnernetz-Stationen), **keine** Live-Warnungen |
| meteoschweiz.admin.ch Produkt-Feed | `product/output/warnings/version__/…`, `home.html?tab=danger` | **404** (versionierte Platzhalter, kein stabiler Pfad) |

## Schlussfolgerung

**Es gibt keinen stabilen, dokumentierten öffentlichen JSON-Feed** für die
aggregierten Schweizer Naturgefahren-/Wetterwarnungen. Die einzigen Wege wären
das Reverse-Engineering undokumentierter, versionierter App-Endpunkte oder das
Parsen geospatialer STAC-Layer — beides fragil und ein Verstoss gegen die
Portfolio-Anti-Patterns («nicht gegen nicht-funktionierende/undokumentierte
Endpunkte bauen»). Zudem sind aggregierte **Wetterwarnungen** (Sturm/Gewitter/
Hitze) laut Zuständigkeitsmatrix Domäne von `meteoswiss-mcp`.

## Architektur-Entscheid

Statt eines fragilen Scrapings werden `env_hazard_overview` /
`env_hazard_regions` zu **netzwerkfreien Orientierungs-/Routing-Tools** umgebaut:

- Sie verweisen deterministisch auf die **dedizierten, live funktionierenden**
  Tools dieses Servers: Hochwasser → `env_flood_warnings`/`env_hydro_current`
  (BAFU/LINDAS), Lawine → `env_avalanche_bulletin` (SLF), Waldbrand →
  `env_wildfire_danger` (waldbrandgefahr.ch), Schnee → `env_snow_current` (SLF).
- Aggregierte Wetter-/Unwetterwarnungen werden sauber an **MeteoSchweiz /
  `meteoswiss-mcp`** verwiesen (Zuständigkeitsmatrix), plus offizielle
  Portallinks.
- Kein Netzwerk-Call mehr → kein toter Endpoint, deterministisch, stabil.

**Konsequenzen:**
- Die REST-Fetcher `fetch_hazard_overview` / `fetch_regional_hazards` sind
  entfernt.
- `www.naturgefahren.ch` ist aus der Egress-Allow-List (`ALLOWED_HOSTS`) und dem
  Network-Policy-Beispiel entfernt (SEC-021: Angriffsfläche minimieren) — die
  Domain erscheint nur noch als Text-Link.
- **Offen (out of scope hier):** Falls strukturierte Live-Wetterwarnungen
  gewünscht sind, gehören sie in `meteoswiss-mcp`, das die (undokumentierte)
  MeteoSchweiz-App-API dort sauber und domänengerecht kapseln kann.
