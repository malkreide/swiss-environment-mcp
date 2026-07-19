# Live-Probe — Eidg. Jagdstatistik

**Datum der Probe:** 2026-07-19
**Prober:** Phase-1-Erweiterung (Skill `mcp-data-source-probe`, Schritt 1)
**Einstieg:** `https://www.jagdstatistik.ch/de/home`
**Ziel:** Abschuss- und Fallwildzahlen je Kanton, Tierart, Jahr.
**Datenherr:** BAFU (Seite trägt `bafu-header-de.png`).

---

## 1. Backend-Lokalisierung

Die Seite ist eine **Web-App mit eigenem Widget-Framework** (jQuery + DataTables +
Highcharts + Mapbox), kein SPA-Framework (Nuxt/Next). Datenzugriff erfolgt über
**Content-Negotiation auf derselben Seiten-URL**:

- Request mit Header `X-Requested-With: XMLHttpRequest` (`Accept: application/json`)
  → Server liefert **JSON** statt HTML.
- Antwort-Schema: `{"controls": { "<name>": {"ctrltype": ..., "ctrldata"/"options": ...} }}`
- Zusätzlicher Hilfsendpoint: `GET /de/api?action=csrftoken` → `{"data":"<token>"}`
  (nur für schreibende/POST-Aktionen nötig; Lesen geht per GET ohne Token).

**Daten-Endpoint:** `GET /de/statistics?<query>` (mit AJAX-Header).

---

## 2. Query-Dimensionen (verifiziert)

Aus den `controls` des Statistics-Endpoints extrahiert:

| Parameter | Control | Bedeutung | Werte (Auszug) |
|---|---|---|---|
| `ar` | `fi-dropdown1` | **Kanton / Gebiet** | `CH`=ganze Schweiz, `AG`, `ZH`, `GR`, … (26 Kantone) |
| `dt` | `fi-dropdown3` | **Datentyp** | **`1`=Abschuss, `2`=Bestand, `3`=Aussetzung, `4`=Fallwild** |
| `sp` | `fi-tree1` | **Tierart** | z. B. `100`=Rothirsch, `305`=Jagdausübende |
| `yrfrom`/`yrto` | `fi-rangeslider1` | **Jahresbereich** | z. B. 2015–2024 |
| `tt` | `fi-radio0` | Tabellentyp/Darstellung | `0`, `1`, … |

Interner State (aus Message-Feldern sichtbar): `tt, dt, at, ar, th, st, sp, dp,
yrfrom, yrto`. Das Jagdjahr dauert «in den meisten Kantonen 1. April–31. März».

---

## 3. Daten-Payload

Die eigentlichen Zahlen liegen im Control **`fi-chart-or-table`** (`bs4chart`),
Feld `ctrldata` = **Highcharts-Konfiguration**:
- `xAxis.categories` = Jahre (z. B. `["2015",…,"2024"]`)
- `series[].name` = Klasse (Alter/Geschlecht bzw. w/m)
- `series[].data` = Zahlenwerte je Jahr

---

## 4. Befund-Tabelle

| Probe | URL | HTTP | Status | Ergebnis |
|---|---|---|---|---|
| Homepage (HTML) | `/de/home` | 200 | ✅ | Web-App, JS-gerendert |
| CSRF-Token | `/de/api?action=csrftoken` | 200 | ✅ | `{"data":"…"}` |
| Home als JSON | `/de/home` + AJAX-Header | 200 | ✅ | `{"controls":{"ja-news":…}}` |
| **Statistics (Struktur)** | `/de/statistics?tt=1&sp=305` + AJAX | 200 | ✅ | 14 Controls, 6 KB; Query-Dims + Chart |
| **Anchor Abschuss** | `/de/statistics?tt=0&sp=100&dt=1&ar=ZH` + AJAX | 200 | ✅ | **Titel «Rothirsch», Untertitel «Abschuss»; Serien Kuhkalb/Stierkalb/… mit Jahreswerten** |
| Kantonsliste | `fi-dropdown1` | 200 | ✅ | CH + 26 Kantone |
| Datentyp-Liste | `fi-dropdown3` | 200 | ✅ | Abschuss/Bestand/Aussetzung/Fallwild |
| Falsche Route | `/de/data`, `/de/table` … | 404 | ✅ | sauberes 404 (HTML) |

### Reality-Check
Kantone (27 inkl. CH), Datentypen (4) und Tierarten-Baum entsprechen der
öffentlichen Auswertungsmaske 1:1. Abschuss-Serien plausibel (mehrjährige Reihen,
Klassen nach Alter/Geschlecht). Daten decken u. a. 2015–2024 ab.

### ⚠️ Fund: undokumentierter, content-negotiierter Backend-Vertrag
Es gibt **keine offizielle API-Doku und keinen OpenAPI-Contract**. Der JSON-Zugang
ist ein Nebenprodukt des Widget-Frameworks (`X-Requested-With`-Umschaltung). Das
Schema (`controls` → Highcharts-`ctrldata`) kann sich bei einem Frontend-Update
**ohne Vorwarnung ändern**. Das Datenmodell ist zudem **Highcharts-zentriert**
(Präsentations- statt Datenschema) — für ein MCP-Tool muss es in ein flaches
`{kanton, tierart, jahr, datentyp, wert}`-Schema **normalisiert** werden.

*Metapher-Fundstück:* «Die Jagdstatistik gibt keine Daten heraus — sie gibt ein
fertiges Diagramm heraus, aus dem wir die Zahlen zurückrechnen müssen.»

---

## 5. Dump-Verfügbarkeit
- **Kein offizieller Bulk-Dump** (kein CSV/JSON-Export-Endpoint gefunden; die
  Frontend-Exportbuttons erzeugen client-seitig PDF/XLSX aus dem geladenen Chart).
- Der einzige maschinelle Zugang ist der content-negotiierte `/de/statistics`.

---

## 6. Architektur-Empfehlung: **Dump-first via Eigen-Harvest (Arch B, Richtung C)**

Weil (a) kein offizieller Dump existiert und (b) der Live-Endpoint undokumentiert
und fragil ist, wird **nicht** direkt live pro Tool-Call abgefragt. Stattdessen:

1. **Harvester** (einmalig/periodisch): systematisch über
   `ar × dt × sp × jahr` iterieren, aus jedem `fi-chart-or-table` die Serien
   extrahieren und in ein **normalisiertes lokales Dump** schreiben
   (`{kanton, tierart, jahr, datentyp, klasse, wert}` → Parquet/JSON).
   Datenmenge klein (27 × 4 × ~30 Arten × ~15 Jahre), Update **jährlich** (Jagdjahr).
2. **MCP-Tools** lesen aus dem gecachten Dump (`provenance: weekly_dump`/`cached`),
   nicht live. Live-`/de/statistics` nur als Best-Effort-Refresh (`live_api`).

| Bedarf | Quelle | Provenance |
|---|---|---|
| Abschuss/Fallwild je Kanton/Art/Jahr | lokaler Harvest-Dump | `weekly_dump` (jährl.) / `cached` |
| Aktualisierung | `/de/statistics` Harvest | `live_api` (Refresh-Job) |

### Resilienz-Hinweise (Schritt 3)
- Retry mit Backoff für jeden Harvest-Call.
- **Schema-Guard:** beim Parsen prüfen, ob `controls.fi-chart-or-table.ctrldata`
  existiert; bei Strukturänderung sprechender Fehler + letzter erfolgreicher
  Harvest-Zeitstempel (Graceful Degradation), nie stille leere Records.
- `X-Requested-With: XMLHttpRequest` ist Pflicht-Header (sonst HTML).
- Attribution: `BAFU — Eidg. Jagdstatistik`. **Lizenz noch verifizieren**
  (Seite nennt keine explizite Lizenz; BAFU-Nutzungsbedingungen/OGD annehmen und
  vor Release bestätigen — Kontakt BAFU/jagdstatistik.ch).
- Neuer Egress-Host: `www.jagdstatistik.ch`.

### Offene Punkte für Phase 2
- Lizenz schriftlich bestätigen (BAFU-Terms vs. OGD).
- Vollständige `sp`-Codeliste (Tierarten-Baum) und `ar`-Codeliste extrahieren und
  als statische Lookup-Tabellen ablegen.
- Semantik `dt=3 Aussetzung` (Wiederansiedlung) dokumentieren.

---

## 7. Architektur-Entscheid (Phase 3, Implementierung 2026-07-19)

**Umgesetzt: Live-Wrapper mit eingebetteten Lookups + Schema-Guard** — eine
**bewusste Abweichung** von der ursprünglichen Dump-first-Empfehlung (Abschnitt 5).

**Begründung:**
- Der Ziel-Runtime ist ein **ephemerer Container** (Cloud/stdio) ohne persistenten
  Datenträger — ein lokal gecachtes Bulk-Dump überlebt einen Neustart nicht und
  brächte gegenüber dem Live-Abruf keinen Robustheitsgewinn.
- Die Payload pro Abfrage ist **klein** (eine Art × Kanton × Datentyp, ~10 Jahre)
  und der Endpoint antwortet zuverlässig < 1 s.
- Die **stabilen Dimensionen** (36 Tierarten, 27 Kantone, Datentypen) sind als
  statische Lookups **eingebettet** (`JAGD_SPECIES`/`JAGD_CANTONS`/`JAGD_DATATYPES`,
  Stand 2026-07-19) — das ist der «Dump-Anteil». Nur die **volatilen Zahlen**
  werden live geholt.

**Fragilität abgesichert (statt durch Dump):**
- **Schema-Guard** in `fetch_jagd_statistics`: fehlt `controls.fi-chart-or-table.
  ctrldata`, liefert die Funktion `found=False` und das Tool degradiert sauber
  («unerwartete Datenstruktur»), statt einen Stacktrace zu werfen.
- **Retry** (429/5xx, Timeout) mit exponentiellem Backoff über `_get_json_retry`.
- Pflicht-Header `X-Requested-With: XMLHttpRequest` zentral in
  `JAGD_AJAX_HEADERS`.

**Verifizierte Parameter-Korrektur gegenüber Abschnitt 2:**
Der Datentyp-Parameter ist **`th`** (nicht `dt`); erst mit `th` greift auch der
Kanton-Filter `ar`. Tierart-Codes sind klein (Reh=`2`, Rothirsch=`1`). Der
Jahresbereich-Parameter (`yr`) verhält sich unzuverlässig und wird **nicht**
exponiert — die Tools liefern die volle Reihe (2015–2024).

### Lizenz-Recherche (2026-07-19)
Nachgeschlagen im Rahmen der Nacharbeiten:
- **Datenherr:** BAFU. Laut Impressum stammen die Daten «von spezialisierten
  kantonalen Stellen»; Programmierung/Applikation durch **Wildtier Schweiz**,
  Betrieb durch das BAFU.
- **Keine explizite Lizenz** auf `jagdstatistik.ch` (Impressum enthält keinen
  Lizenz-/Copyright-/Nutzungshinweis für die Daten).
- **Nicht als lizenzierter Datensatz auf opendata.swiss** publiziert — dort finden
  sich unter dem BAFU nur Jagd-*Geodaten* (Jagdbanngebiete), nicht die
  Abschuss-/Fallwild-*Statistik*.
- **Folge für den Server:** Jede Antwort trägt die Quellenangabe zum BAFU
  (`_JAGD_ATTRIBUTION`). Eine formelle Lizenzbestätigung (BAFU-Terms/OGD) kann nur
  das BAFU selbst geben und bleibt offen (Kontakt: über bafu.admin.ch).

**Bleibt offen:** Formelle Lizenzbestätigung durch das BAFU (BAFU-Terms/OGD) vor einem
produktiven Release — in den READMEs unter «Known Limitations» vermerkt.
