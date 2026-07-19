# Live-Probe — BAFU Hydrodaten via LINDAS (SPARQL)

**Datum der Probe:** 2026-07-19
**Prober:** Phase-1-Erweiterung (Skill `mcp-data-source-probe`, Schritt 1)
**Einstieg:** `https://environment.ld.admin.ch/.well-known/void/dataset/hydro`
**Ziel:** Pegel-/Abflussmessstationen, aktuelle Werte, Zeitreihen, Wassertemperatur.

---

## 1. Endpoint-Ermittlung (verifiziert, nicht angenommen)

Der `void`-Deskriptor (`Accept: text/turtle`, HTTP 200, 6 KB) deklariert:

| Feld | Wert |
|---|---|
| `void:sparqlEndpoint` | `https://politics.ld.admin.ch/query/` (Alias) |
| Kanonischer Endpoint | **`https://lindas.admin.ch/query`** (via `schema:workExample`) |
| Named Graph | `<https://lindas.admin.ch/foen/hydro>` |
| Teile (`schema:hasPart`) | `.../foen/hydro/river`, `.../foen/hydro/lake` |
| Titel | «Aktuelle hydrologische Messwerte des BAFU» |
| `dcterms:license` | `https://ld.admin.ch/vocabulary/TermsOfUse/Open-Use` → **OGD-CH / Open-Use** |
| Kontakt | Hydrologische Abfragezentrale, abfragezentrale@bafu.admin.ch |
| `schema:dateModified` | 2026-07-19T13:24 (⇒ täglich/laufend aktualisiert) |

Der Endpoint ist ein **Fuseki-kompatibler SPARQL-1.1-Endpoint**. Query via
`POST`/`GET` mit `query=`-Parameter und `Accept: application/sparql-results+json`.
Antwortzeit durchgehend **< 1 s**.

---

## 2. Vokabular (exploratives SPARQL, nicht Doku-Annahme)

Der Graph verwendet das **RDF-Data-Cube-Vokabular `cube.link`** von LINDAS.

### Klassen im Graph `<https://lindas.admin.ch/foen/hydro>`

| Klasse | Anzahl | Bedeutung |
|---|---|---|
| `http://example.com/HydroMeasuringStation` | 233 | Messstationen |
| `https://cube.link/Observation` | 233 | aktueller Messwert je Station |
| `http://schema.org/BodyOfWater` | 162 | Gewässer |
| `https://cube.link/Cube` | 2 | River-Cube + Lake-Cube |
| `https://cube.link/MeasureDimension` | 6 | Messgrössen (siehe unten) |

### Station (`HydroMeasuringStation`) — Properties

| Property | Beispiel |
|---|---|
| `schema:name` | «Zürich Unterhard» |
| `schema:identifier` | `2099` — **= BAFU-Stationsnummer** (identisch zur bestehenden REST-API!) |
| `schema:containedInPlace` | `.../waterbody/Limmat` |
| `geosparql:hasGeometry` | Punktgeometrie (WGS84) |
| `schema:inDefinedTermSet` | `.../measuring-stations` |

### Observation — Dimensions (`.../foen/hydro/dimension/...`)

| Dimension | Cube | Einheit / Wertebereich |
|---|---|---|
| `station` | beide | Verweis auf Station |
| `measurementTime` | beide | ISO-Zeitstempel (+01:00) |
| `waterLevel` (Wasserstand) | River + Lake | m ü. M. |
| `discharge` (Abfluss) | River | m³/s |
| `waterTemperature` (Wassertemperatur) | River | °C |
| `dangerLevel` (Gefahrenstufe) | beide | 1–5 bzw. `cube.link/Undefined` |

- **River-Cube:** discharge + waterLevel + waterTemperature + dangerLevel
- **Lake-Cube:** waterLevel + dangerLevel

Mehrsprachige Labels (de/fr/it/en) sind an den `MeasureDimension`-Termen hinterlegt.

---

## 3. Befund-Tabelle

| Probe | Query | HTTP | Status | Ergebnis |
|---|---|---|---|---|
| Endpoint erreichbar | Klassen-Zählung im Graph | 200 | ✅ | 17 Klassen, < 1 s |
| Stations-Metadaten | Properties `HydroMeasuringStation` | 200 | ✅ | name/id/waterbody/geometry |
| Aktuelle Werte | Properties `Observation` | 200 | ✅ | station/time/level/discharge/temp/danger |
| Messgrössen-Abdeckung | `COUNT` je Dimension | 200 | ✅ | 187 mit Abfluss, 81 mit Temperatur, 233 mit Pegel |
| **Anchor (aktuell)** | Limmat @ Zürich, aktueller Abfluss | 200 | ✅ | Station **2099 «Zürich Unterhard», Abfluss 34.997 m³/s** @ 2026-07-19T14:20 |
| Gewässer-Filter | alle Limmat-Stationen | 200 | ✅ | 2099 (Zürich Unterhard), 2243 (Baden, Limmatpromenade) |
| **Zeitreihe (historisch)** | `COUNT` Observations je Station | 200 | ⚠️ | **exakt 1 Observation/Station** — nur letzter Wert |
| Zeit-Range | MIN/MAX `measurementTime` | 200 | ⚠️ | 2025-05 … 2026-07, aber Snapshot (kein Verlauf) |
| Fehlerfall | absichtlich fehlerhaftes SPARQL | 400 | ✅ | `MALFORMED QUERY: Encountered "<EOF>"` — sauberer Fehler |

### Reality-Check
233 Stationen entsprechen der Grössenordnung des BAFU-Messnetzes (Homepage nennt
«rund 260» inkl. Grundwasser/Qualität). Plausibel: LINDAS bildet das öffentliche
Oberflächengewässer-Netz ab.

### ⚠️ Kritischer Fund: LINDAS = **nur aktuelle Werte, keine Zeitreihe**
Der Graph «Aktuelle hydrologische Messwerte» enthält pro Station **genau eine
Observation** (der jeweils letzte Messwert). Es gibt **keine historischen
Tages-/Stundenmittel** in LINDAS. Die Anchor-Frage
(«Abflussmenge der Limmat im **Sommer 2024** vs. **langjähriges Mittel**»)
ist damit über LINDAS **nicht** vollständig beantwortbar — LINDAS liefert nur
den *heutigen* Wert.

*Metapher-Fundstück:* «LINDAS-Hydro ist ein Live-Ticker, kein Archiv — es zeigt
den Puls, nicht die Krankengeschichte.»

---

## 4. Dump-Verfügbarkeit / historische Daten

- **LINDAS selbst:** kein Bulk-Dump nötig für aktuelle Werte (SPARQL liefert alle
  233 Stationen in einem Query).
- **Historische Zeitreihen** (für Anchor «Sommer 2024 / langjähriges Mittel»):
  nicht in LINDAS. Bezugsquellen:
  - BAFU Hydrologisches Jahrbuch / Tagesmittelwerte ab 1900 via **opendata.swiss**
    (der bestehende Server referenziert diese CSV bereits in `env_hydro_history`).
  - Diese liegen bereits im Egress-Scope (`opendata.swiss`).

---

## 5. Architektur-Empfehlung: **Hybrid (Arch B) — SPARQL-first für Live, Dump für Historie**

| Bedarf | Quelle | Provenance |
|---|---|---|
| Aktueller Pegel/Abfluss/Temperatur/Gefahrenstufe | **LINDAS SPARQL** (`live_api`) | typisiert, sub-sekündlich |
| Stations-Metadaten (Name, Gewässer, Geo, ID) | **LINDAS SPARQL** (`live_api`) | ersetzt fragiles Scraping |
| Historische Zeitreihe / langjähriges Mittel | opendata.swiss CSV (`weekly_dump`/`cached`) | für Trend-/Vergleichsfragen |

**Begründung:**
1. LINDAS ist gegenüber dem heutigen `hydrodaten.admin.ch`-JSON-Scraping (siehe
   `api_client.fetch_hydro_stations` / `fetch_hydro_station_data`) **robuster und
   sauberer typisiert** — feste `cube.link`-Dimensionen statt „flexible Struktur
   je nach API-Version". Empfehlung: LINDAS als primären Live-Pfad einführen,
   den REST-Pfad als Fallback behalten.
2. Die Station-`identifier` sind **identisch** zu den bereits verwendeten
   BAFU-Nummern (2099 = Limmat/Zürich) — nahtlose Migration, keine ID-Übersetzung.
3. Der historische Teil der Anchor-Frage bleibt bewusst beim CSV-Dump-Pfad;
   LINDAS deckt ihn nicht ab (⇒ in «Known Limitations» dokumentieren).

### Client-Wiederverwendung (Phase-2-Aufgabe)
Der Skill-Hinweis verlangt: **SPARQL-Client-Aufbau des bestehenden `fedlex-mcp`
analysieren und wiederverwenden**, statt neu zu bauen. `fedlex-mcp` liegt in
einem separaten Repo (nicht im aktuellen Session-Scope). Phase-2-Action:
`fedlex-mcp`-Repo hinzuziehen, dessen SPARQL-Client (POST-Query,
`sparql-results+json`-Parsing, Retry/Timeout) in ein gemeinsames
`sparql_client.py` extrahieren. Bis dahin: SPARQL-Host
`lindas.admin.ch` in die Egress-Allow-List (`api_client.ALLOWED_HOSTS`)
aufnehmen und den bestehenden `_fetch_with_retry`-Pfad (2 s/4 s/8 s Backoff)
wiederverwenden.

### Resilienz-Hinweise (Schritt 3)
- Retry mit exponentiellem Backoff auch für SPARQL-POST (Fuseki liefert bei Last
  gelegentlich 503).
- `provenance: live_api` in jeder LINDAS-Response.
- Attribution: `BAFU — hydrologische Daten, Open-Use (OGD-CH)`.
- Graceful Degradation: bei SPARQL-Ausfall auf REST-`hydrodaten.admin.ch`-Pfad
  zurückfallen und Provenance entsprechend kennzeichnen.

---

## 6. Verifizierte Beispiel-Query (aktueller Limmat-Abfluss)

```sparql
PREFIX s:  <http://schema.org/>
PREFIX hd: <https://environment.ld.admin.ch/foen/hydro/dimension/>
SELECT ?id ?name ?discharge ?temp ?level ?t
FROM <https://lindas.admin.ch/foen/hydro>
WHERE {
  ?st a <http://example.com/HydroMeasuringStation> ;
      s:identifier ?id ; s:name ?name ;
      s:containedInPlace ?wb .
  ?obs hd:station ?st ; hd:measurementTime ?t .
  OPTIONAL { ?obs hd:discharge        ?discharge }
  OPTIONAL { ?obs hd:waterTemperature ?temp }
  OPTIONAL { ?obs hd:waterLevel       ?level }
  FILTER(CONTAINS(STR(?wb), "Limmat"))
}
```
→ liefert 2099 «Zürich Unterhard» (Abfluss) und 2243 «Baden, Limmatpromenade».
