# Live-Probe — SLF Datenservice (Schnee & Lawinen)

**Datum der Probe:** 2026-07-19
**Prober:** Phase-1-Erweiterung (Skill `mcp-data-source-probe`, Schritt 1)
**Einstieg:** `https://www.slf.ch/en/services-and-products/slf-data-service/`
**Ziel:** Schneehöhen, Neuschnee, Lawinenwarnstufen je Station/Region.
**Auth-Prüfung:** ✅ **öffentliches Mess-API ohne Auth vorhanden.**

---

## 1. Ermittelte Endpoints (aus der Doku-Seite, alle no-auth)

| Zweck | Basis-URL | Format |
|---|---|---|
| **Live-Mess-API (OpenAPI)** | `https://measurement-api.slf.ch/` | JSON (ReDoc/OpenAPI 1.1.0) |
| Historische Rohdaten | `https://measurement-data.slf.ch` | CSV/Download |
| **Lawinenbulletin** | `https://aws.slf.ch/api/bulletin/caaml` | CAAML (XML/JSON) |
| Bulletin-Produkte (PDF, Karten) | `https://aws.slf.ch/api/bulletin/document/` | PDF/PNG |
| **Warnregionen** | `https://aws.slf.ch/api/warningregion/` | GeoJSON / KML (Swagger UI) |
| Extremwertanalyse | `https://extreme-value-analysis.slf.ch` | Gumbel-/Winter-Plots |

**Lizenz:** **CC BY 4.0** — Attribution «WSL-Institut für Schnee- und
Lawinenforschung SLF» erforderlich; wissenschaftliche Nutzung mit DOI-Zitat.
Kein API-Key, keine Registrierung (Registrierung nur optional für Mailingliste).

---

## 2. Verifizierte Endpoints (`measurement-api.slf.ch`, OpenAPI 1.1.0)

OpenAPI-Spec unter `/openapi.json` (HTTP 200, 14 KB). Alle Pfade **`GET`, no-auth**:

| Pfad | Zweck |
|---|---|
| `/public/api/imis/stations` | Automatische IMIS-Stationen (Metadaten) |
| `/public/api/imis/measurements` | Aktuelle IMIS-Messwerte |
| `/public/api/imis/station/{station_code}/measurements` | Werte je Station |
| `/public/api/imis/daily-snow` | **Tages-Schneewerte aller Stationen** |
| `/public/api/imis/measurements-precipitation` | Niederschlag (⚠️ siehe Abgrenzung) |
| `/public/api/imis/station/{code}/measurements-precipitation` | Niederschlag je Station |
| `/public/api/study-plot/stations` | Manuelle Beobachtungsfelder |
| `/public/api/study-plot/measurements` | Manuelle Messwerte (Schneehöhe/Neuschnee) |
| `/public/api/study-plot/station/{code}/measurements` | Werte je Beobachtungsfeld |

---

## 3. Befund-Tabelle

| Endpoint | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `/openapi.json` | 200 | ✅ | – | OpenAPI 1.1.0, 9 Pfade |
| `/public/api/imis/stations` | 200 | ✅ | ~viele | JSON: `code,label,lon,lat,elevation,canton_code,type` |
| `/public/api/imis/daily-snow` | 200 | ✅ | alle Stat. | JSON: `station_code,measure_date,HS,HN_1D` |
| `aws.slf.ch/api/warningregion/` | 200 | ✅ | – | Swagger UI ⇒ GeoJSON/KML der Warnregionen |
| `aws.slf.ch/api/bulletin/caaml` | 200 | ✅ | – | Bulletin-API (CAAML) |
| `/public/api/imis/station/…/measurements` (falsche ID) | 404 | ✅ | – | sauberes JSON `{"detail":"Not Found"}` (FastAPI) |

### Felder-Fund (Schnee)
- `HS` = **Schneehöhe** (Höhe der Schneedecke)
- `HN_1D` = **Neuschnee 24 h**
- `type` der Station: z. B. `SNOW_FLAT`, `WIND` — Sensortyp; für Schneehöhe
  `SNOW_FLAT`-Stationen filtern.
- `canton_code` vorhanden ⇒ kantonale Aggregation direkt möglich.

### Reality-Check / saisonale Einschränkung
Probe im **Juli**: `daily-snow` liefert korrekt `HS=0.0, HN_1D=0.0` (schneefrei).
Das **Lawinenbulletin** (`caaml`) wird nur in der Wintersaison publiziert —
Lawinenwarnstufen sind ausserhalb der Saison leer. Das ist **kein Fehler**,
sondern der reguläre Saisonzyklus (analog zur bestehenden `env_hazard_*`-Logik).

---

## 4. Dump-Verfügbarkeit
- Kein separater Bulk-Dump nötig: `measurement-data.slf.ch` bietet historische
  CSV-Downloads, und `/daily-snow` liefert bereits **alle Stationen in einem Call**.
- Das API *ist* der Bulk-Zugang (batch-fähig).

---

## 5. Architektur-Empfehlung: **API-first (Arch A)**

Sauber dokumentiertes OpenAPI, no-auth, stabile JSON-Schemas, batch-fähig,
CC-BY-lizenziert. Kein Dump-Fallback erforderlich.

| Bedarf | Endpoint | Provenance |
|---|---|---|
| Schneehöhe / Neuschnee je Station | `/public/api/imis/daily-snow`, `study-plot/measurements` | `live_api` |
| Stationsliste (Kanton/Höhe/Typ) | `/public/api/imis/stations` | `live_api` |
| Lawinenwarnstufe je Region | `aws.slf.ch/api/bulletin/caaml` + `warningregion` | `live_api` (saisonal) |

### Resilienz-Hinweise (Schritt 3)
- Retry mit Backoff (2/4/8 s) — SLF-Endpoints hinter CDN, transiente 5xx möglich.
- `provenance: live_api`; Attribution: `SLF (WSL) — CC BY 4.0`.
- Graceful Degradation: ausserhalb der Lawinensaison klare Meldung
  «kein aktives Bulletin» statt leerer Records.
- Neue Egress-Hosts: `measurement-api.slf.ch`, `aws.slf.ch`
  (und optional `measurement-data.slf.ch`) in `ALLOWED_HOSTS` aufnehmen.

---

## 6. ⚠️ Abgrenzung zu `meteoswiss-mcp` (Zuständigkeitsmatrix — Phase 2)

SLF liefert **Niederschlag** (`measurements-precipitation`) und **Schnee** —
beides potenziell überschneidend mit `meteoswiss-mcp`. Vorschlag für die
Zuständigkeitsmatrix (in **beide** READMEs unter «Known Limitations»):

| Grösse | Zuständig | Nicht zuständig |
|---|---|---|
| **Schneehöhe / Neuschnee (Boden, Station)** | **swiss-environment (SLF)** | meteoswiss |
| **Lawinenwarnstufe** | **swiss-environment (SLF)** | meteoswiss |
| **Niederschlag (meteorolog. Messnetz, Prognose)** | **meteoswiss** | swiss-environment |
| Niederschlag an IMIS-Bergstationen (Rohsensor) | swiss-environment (SLF, nur als Kontext zum Schnee) | — |
| Temperatur/Wind (Wetter) | meteoswiss | swiss-environment |

**Regel:** `swiss-environment-mcp` = **Schnee-/Lawinengefahr** (SLF-Domäne).
`meteoswiss-mcp` = **Wetter & Niederschlagsmessnetz/-prognose**. Der
`measurements-precipitation`-Endpoint wird — wenn überhaupt — nur als
Begleitgrösse zur Schneedecke eingebunden, **nicht** als Niederschlags-Tool
(sonst Duplikation mit meteoswiss).
