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

---

# Nachtrag 2026-07-24 — Cube-Ebene, observationSet, Versionierung, Lizenz

**Anlass:** Erweiterungsauftrag «BAFU-Hydrodaten via LINDAS» mit sechs generischen
LINDAS-Fundstücken (Cube-Verankerung, Codes statt Labels, BFS-Nummern in URIs,
Fünfsprachigkeit, Cube-Versionierung, observationSet-Zwischenschritt). Dieser
Nachtrag prüft die Fundstücke gegen die konkreten Hydro-Cubes und schliesst die
noch offenen Phase-1-Fragen (Cube-Suche inkl. Grundwasser, Struktur via
`observationConstraint`, Phase-2-Zugriff, Zuständigkeitsmatrix). Alle Queries
am 2026-07-24 live verifiziert, Antwortzeiten durchgehend < 2 s.

## N1. Hydro-Cube-Inventar (verankerte Suche)

Verankerte Cube-Suche (`?cube a cube:Cube`) über `schema:name` in allen Sprachen
nach *abfluss / wasser / pegel / hydro / grundwasser / souterrain / groundwater /
nappe / gewässer / fluss*:

| Cube | Inhalt | Versionierung | Status |
|---|---|---|---|
| `.../foen/hydro/river` | Aktuelle Messwerte Flüsse (199 Obs.) | **unversioniert** | ⚠️ `CreativeWorkStatus/Draft` |
| `.../foen/hydro/lake` | Aktuelle Messwerte Seen | **unversioniert** | ⚠️ `CreativeWorkStatus/Draft` |
| `.../foen/ubd01041prod/1…13` | **Badegewässerqualität** (E.coli, Enterokokken) | 13 Versionen | `Published` |
| `.../foen/ubd0104/1…6` | Badegewässerqualität (Vorgänger-Serie) | 6 Versionen | `Published` |

**Negativ-Befund Grundwasser:** Es existiert **kein Grundwasser-Cube** in LINDAS
(mehrsprachig geprüft). Grundwasserstände sind nur ausserhalb LINDAS verfügbar
(BAFU-Grundwasserbeobachtung NAQUA, kein SPARQL). → Known Limitation.

**Nicht-Cube-Vokabular:** Wie in Abschnitt 2 dokumentiert, hängen die
Stationsdaten an einer eigenen Klasse `HydroMeasuringStation` (233 Instanzen)
*neben* den Cubes — Fundstück «Hydro-Daten evtl. nicht als Cube» trifft für die
Stammdaten zu, für die Messwerte nicht.

## N2. Struktur via `observationConstraint` (Phase-1-Zugriff)

Beide Muster-Cubes liefern die Struktur sauber über
`cube:observationConstraint / sh:property`:

**`foen/hydro/river`:** Key = `station`, `measurementTime`; Measures =
`discharge` (m³/s), `waterLevel` (m ü. M.), `waterTemperature` (°C),
`dangerLevel` (1–5). Deckt sich mit Abschnitt 2.

**`foen/ubd01041prod/13`:** Key = `dateofprobing`, `parametertype`
(`E.coli`|`Enterokokken`, als String — kein Code), `location` (**URI-Code**,
s. N4); Measure = `value` (Konzentration); dazu `lowerlod`/`upperlod`
(Bestimmungsgrenzen, weder Key noch Measure).

## N3. observationSet-Zwischenschritt (Fundstück 6) — **bestätigt**

Am River-Cube live gemessen:

| Zugriffspfad | Zeilen |
|---|---|
| `?cube cube:observation ?obs` (direkt) | **0** |
| `?cube cube:observationSet ?set . ?set cube:observation ?obs` | **199** |

Der Direktzugriff liefert NULL Zeilen ohne Fehlermeldung — der
`observationSet`-Zwischenschritt ist zwingend. (Die Queries in Abschnitt 6
umgehen das Problem, weil sie über die Dimensions-Property `hd:station` statt
über den Cube einsteigen — beide Pfade sind gültig, der Cube-Direktpfad nicht.)

## N4. Codes → Labels (Fundstück 2) — für Badegewässer bestätigt

`foen/hydro`-Observations tragen direkt Literalwerte (kein Code-Problem).
`ubd01041prod` dagegen liefert die Ortsdimension als **Code-URI**:

```
location = https://ld.admin.ch/dimension/bgdi/inlandwaters/bathingwater/CH22088
```

Auflösung über ein zweites Pattern (`?loc schema:name ?label`):
`CH22088` → **«Clendy»**, mit `schema:containedInPlace` →
`https://ld.admin.ch/canton/22` (**Kantonsnummer im URI-Klartext** — Join-Key,
analog Fundstück 3 zu Gemeinde-BFS-Nummern) sowie WGS84-Koordinaten.
Code→Label-Auflösung ist damit für jeden künftigen Cube-generischen Zugriff
Pflicht; für die beiden `foen/hydro`-Cubes genügt der Stations-Join.

## N5. Versionierung (Fundstück 5) — Dedup-Regel

`ubd01041prod` zeigt das Muster: Jede Version trägt `schema:version` (1…13);
**abgelöste Versionen erhalten `schema:expires`**, die aktuelle nicht.
Dedup-Regel für search/get: `FILTER NOT EXISTS { ?cube schema:expires ?x }`
(robuster als MAX über das URI-Suffix, das mal mit, mal ohne Trailing-Slash
vorkommt: `ubd0104/4/` vs. `ubd01041prod/13`).
Die beiden `foen/hydro`-Cubes sind unversioniert (Live-Snapshots) — dort
entfällt die Deduplizierung, dafür ist ihr `Draft`-Status zu dokumentieren.

## N6. Aktualität & Zeitreihen-Fähigkeit

| Cube | Observations | Zeitraum | Charakter |
|---|---|---|---|
| `foen/hydro/river` | 1 je Station | nur letzter Messwert | **Live-Ticker** |
| `ubd01041prod/13` | **12 167** | 2020 → 2025-09-23 | **echte Zeitreihe** |

Der kritische Fund aus Abschnitt 3 bleibt bestehen: Für Pegel/Abfluss gibt es
in LINDAS keine Historie. Die Badegewässerqualität ist dagegen als
Mehrjahres-Zeitreihe abfragbar (Saison-Daten, jährliche Nachführung —
`dcterms:modified` 2026-05, letzte Probe 2025-09). Die Anchor-Frage
(«aktueller Abfluss vs. langjähriges Mittel») bleibt via LINDAS **nur zur
Hälfte** beantwortbar — ehrlich reduziert auf: aktueller Abfluss (LINDAS) +
Verweis auf BAFU-Tagesmittel-CSV für das langjährige Mittel.

## N7. Lizenz — liegt am Graph bzw. Datensatz, nicht am Cube

- `foen/hydro`: `dcterms:license` + `dcterms:rights` =
  `https://ld.admin.ch/vocabulary/TermsOfUse/Open-Use` — aber am **Named Graph**
  `<https://lindas.admin.ch/foen/hydro>`, nicht an den Cube-URIs.
- `ubd01041prod/13`: **keine** Lizenz-Triple am Cube; Herkunft nur über
  `dcterms:creator/publisher` (BAFU) und `schema:workExample` → opendata.swiss.

Konsequenz für die Implementation: Lizenzfeld je Antwort aus dem Graph bzw.
Datensatz-Deskriptor ziehen; wo keines deklariert ist, explizit
`«Lizenz: nicht am Cube deklariert — Herkunft BAFU, via opendata.swiss prüfen»`
ausgeben statt stillschweigend «Open-Use» anzunehmen.

## N8. Zuständigkeitsmatrix BAFU (LINDAS) vs. MeteoSchweiz

Konkret gegen die Cube-Dimensionen geprüft — **keine Messgrössen-Überschneidung**:

| Messgrösse | BAFU via LINDAS (`swiss-environment-mcp`) | MeteoSchweiz (`meteoswiss-mcp`) |
|---|---|---|
| Abfluss (m³/s) | ✅ `hydro/river` | ❌ |
| Wasserstand / Pegel (m ü. M.) | ✅ `hydro/river` + `lake` | ❌ |
| Wassertemperatur (°C) | ✅ `hydro/river` | ❌ (misst Lufttemperatur) |
| Hochwasser-Gefahrenstufe | ✅ `dangerLevel` | ❌ (Wetterwarnungen: Sturm/Gewitter/Hitze) |
| Badegewässerqualität (E.coli u. a.) | ✅ `ubd0104` | ❌ |
| Niederschlag (mm) | ❌ (in keinem Hydro-Cube enthalten) | ✅ |
| Schneefall / Lufttemperatur | ❌ | ✅ |

Die Matrix bestätigt die bereits in `docs/tool-inventory.md` (Abschnitt 3)
dokumentierte Aufteilung; die einzige Duplikationsgefahr (Niederschlag) betrifft
SLF-IMIS, nicht LINDAS.

## N9. Konsequenz für Phase 2 (Stand der Implementation)

Die LINDAS-Anbindung der beiden `foen/hydro`-Cubes ist seit PR #24–#28
**bereits produktiv** (`env_hydro_stations/current/history`,
`env_flood_warnings` LINDAS-first; gemeinsamer `sparql_client.py`, vendored
byte-identisch mit `fedlex-mcp`). Offen wäre gemäss Erweiterungsauftrag:

1. Restrukturierung in ein extraktionsfähiges `lindas/`-Modul
   (`client.py` = HTTP/SPARQL, `cube.py` = cube.link-Guardrails mit
   Zwei-Phasen-Zugriff, Versions-Dedup, Code→Label) — ein **Refactoring**
   des bestehenden Pfads, kein Neubau.
2. Neue Tools nur dort, wo sie nicht mit den bestehenden `env_hydro_*`-Tools
   kollidieren (Tool-Budget 18, aktuell 17): einziger echter Neuzugang wäre
   Badegewässerqualität (`ubd0104`) — der einzige Hydro-Cube mit Zeitreihe.

Entscheid dazu beim «go» für Phase 2.
