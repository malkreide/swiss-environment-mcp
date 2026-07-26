# Live-Probe — naturgefahren.ch & waldbrandgefahr.ch (Endpoint-Drift)

**Datum:** 2026-07-26
**Anlass:** Der nächtliche Live-Test schlug fehl; die Naturgefahren-/Waldbrand-
Tools trafen geänderte Upstream-Endpunkte. Diese Probe klärt den Ist-Zustand
und begründet die daraus folgenden Fixes.

## Befund-Tabelle

| Tool | Alter Endpoint | HTTP | Neuer Zugang | Ergebnis |
|---|---|---|---|---|
| `env_wildfire_danger` | `waldbrandgefahr.ch/api/danger` | 404 | Startseite → `data-react-props` (`warnMapJsonPath`) → signierte ActiveStorage-Blob-JSON | ✅ **gefixt** — 143 Regionen mit Stufe 1–5, Kanton-Mapping aus `cantons` |
| `env_hazard_overview` | `naturgefahren.ch/api/v1/warnings/overview/ch` | 301→404 | keiner gefunden (SPA ohne eingebettete Warndaten) | ⚠️ **abgekündigt** — Tool degradiert auf Direktlinks |
| `env_hazard_regions` | `naturgefahren.ch/api/v1/warnings/regions` | 301→404 | wie oben | ⚠️ **abgekündigt** — Direktlinks |

## Details

### waldbrandgefahr.ch — neue Architektur (Rails/React)
Der REST-Endpoint `/api/danger` ist weg (404). Die Seite ist neu eine
Rails/React-App **ohne stabile JSON-API**: Die Gefahrenstufen liegen unter einer
*signierten* ActiveStorage-Blob-URL
(`/rails/active_storage/blobs/proxy/<signed>/fire_warn_levels-<ts>.json`), deren
Pfad **nicht rät-bar** ist — er steht im `data-react-props`-Attribut der
Startseite (Feld `warnMapJsonPath`), zusammen mit dem Kanton-Mapping
(`cantons`: `id → abbr`). Zugriff daher **zweistufig**: Startseite laden →
`data-react-props` parsen → Blob-JSON laden. Das Blob-JSON ist eine Liste je
Region: `region_name_{de,fr,it,en}`, `canton_id`, `level` (1–5), `valid_from`.

*Fundstück:* «waldbrandgefahr.ch hat keine API mehr — die Daten verstecken sich
im HTML der Startseite, hinter einer täglich neu signierten Blob-URL.» → Der
Vertrag ist HTML-getragen und fragil (analog `jagdstatistik.ch`); im Client
greift ein Schema-Guard (`found=False` → Aufrufer degradiert graceful).

### naturgefahren.ch — API ersatzlos stillgelegt
`/api/v1/warnings/overview/ch` und `/api/v1/warnings/regions` liefern 301
(Query-Param wird verworfen, Downgrade auf `http://`) → dann 404. Die neue
Startseite ist server-gerendert und bettet **keine** Warndaten oder einen
discovery-baren JSON-Pfad ein (geprüft: Homepage-HTML, JS-Bundle, `data-*`).
Die *autoritative* maschinenlesbare Quelle für die Schweizer
Naturgefahren-Warnungen ist **MeteoSchweiz** — das überschneidet aber die
Zuständigkeit von `meteoswiss-mcp` (Wetterwarnungen, siehe
Zuständigkeitsmatrix). Ein Repointing auf MeteoSchweiz ist daher ein grösserer,
portfolio-übergreifender Schritt und bleibt ein **Follow-up**.

**Konsequenz:** `env_hazard_overview` / `env_hazard_regions` behalten ihr
Graceful-Degradation-Verhalten (kuratierte Direktlinks zur Warnplattform, seit
OBS-001 als `isError:true`-Antwort). Sie sind damit funktional (kein Crash,
nützliche Links), liefern aber bis zum MeteoSchweiz-Follow-up keine
strukturierten Live-Warndaten. In den READMEs unter «Known Limitations»
dokumentiert.
