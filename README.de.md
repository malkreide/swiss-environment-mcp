[🇬🇧 English Version](README.md)

> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# 🌿 swiss-environment-mcp

![Version](https://img.shields.io/badge/version-0.6.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![CI](https://github.com/malkreide/swiss-environment-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-environment-mcp/actions)
[![Datenquelle](https://img.shields.io/badge/Daten-BAFU%20%2F%20opendata.swiss-green)](https://opendata.swiss/de/organization/bafu)

> MCP-Server, der KI-Modelle mit Schweizer Umweltdaten des BAFU verbindet – Luftqualität, Hydrologie, Naturgefahren, Waldbrandgefahr und offene Umweltdatensätze.

<p align="center">
  <img src="assets/demo.svg" alt="Demo: Claude fragt die NABEL-Luftqualität über einen swiss-environment-mcp Tool-Call ab und erhält einen WHO-2021-Grenzwertcheck" width="820">
</p>

---

## Übersicht

**swiss-environment-mcp** gibt KI-Assistenten wie Claude direkten Zugriff auf Echtzeit-Umweltdaten der Schweizer Bundesbehörden – ohne API-Keys. Luftqualitätsmessungen des nationalen NABEL-Messnetzes, hydrologische Messstationen, Naturgefahren-Bulletins und der vollständige BAFU-Datenkatalog sind über eine einzige standardisierte MCP-Schnittstelle zugänglich.

Der Server deckt vier thematische Cluster ab: Luftqualität (NABEL), Hydrologie, Naturgefahren und den BAFU-Open-Data-Katalog. Jeder Cluster entspricht einer Gruppe zweckgerichteter Tools, die Rohdaten der Bundesbehörden in saubere JSON-Antworten übersetzen.

**Anker-Demo-Abfrage:** *«Wie ist die aktuelle Luftqualität an der NABEL-Station Zürich-Kaserne – und hält sie die WHO-2021-Richtwerte ein?»*
→ [Weitere Anwendungsbeispiele nach Zielgruppe](./EXAMPLES.md) →

---

## Funktionen

- 🌬️ **Luftqualitäts-Monitoring** – 16 NABEL-Stationen, NO₂/O₃/PM10/PM2.5/SO₂/CO, Schweizer LRV- und WHO-2021-Grenzwertprüfung
- 💧 **Hydrologie** – Pegel, Abfluss, Temperaturen an Schweizer Messstationen
- 🚨 **Hochwasserwarnungen** – aktive Warnungen nach Gefahrenstufe (schweizweit)
- 🏔️ **Naturgefahren-Bulletin** – SLF/BAFU-Bulletin auf DE/FR/IT/EN, regionsspezifische Warnungen
- 🔥 **Waldbrandgefahr** – Kantons- und Regionalindex für Waldbrandgefahr
- ❄️ **Schnee & Lawinen (SLF)** – Schneehöhe, Neuschnee je IMIS-Station; Lawinenwarnstufen (EAWS)
- 🦌 **Jagdstatistik** – Abschuss- & Fallwildzahlen je Tierart, Kanton und Jahr (Eidg. Jagdstatistik)
- 📦 **BAFU-Open-Data-Katalog** – Umweltdatensätze suchen und abrufen via CKAN
- 🔑 **Keine Authentifizierung erforderlich** – alle Datenquellen sind öffentlich zugänglich
- ☁️ **Dual Transport** – stdio für Claude Desktop, Streamable HTTP/SSE für Cloud-Deployment

---

## Voraussetzungen

- Python 3.11+
- Keine API-Keys erforderlich – alle Endpunkte sind ohne Authentifizierung öffentlich zugänglich

---

## Installation

```bash
# Repository klonen
git clone https://github.com/malkreide/swiss-environment-mcp.git
cd swiss-environment-mcp

# Installieren
pip install -e .
```

Oder mit `uvx` (ohne dauerhafte Installation):

```bash
uvx swiss-environment-mcp
```

Oder via pip:

```bash
pip install swiss-environment-mcp
```

---

## Schnellstart

```bash
# Server starten (stdio-Modus für Claude Desktop)
swiss-environment-mcp
```

Sofort in Claude Desktop ausprobieren:

> *«Wie ist die aktuelle Luftqualität an der NABEL-Station Zürich-Kaserne?»*
> *«Gibt es aktuell aktive Hochwasserwarnungen in der Schweiz?»*
> *«Wie hoch ist die Waldbrandgefahr im Kanton Wallis?»*

---

## Konfiguration

### Claude Desktop

**Minimal (empfohlen):**

```json
{
  "mcpServers": {
    "swiss-environment": {
      "command": "uvx",
      "args": ["swiss-environment-mcp"],
      "env": {}
    }
  }
}
```

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Nach dem Speichern Claude Desktop vollständig neu starten.

### Cloud-Deployment (SSE für Browser-Zugriff)

Für den Einsatz via **claude.ai im Browser** (z. B. auf verwalteten Arbeitsplätzen ohne lokale Software-Installation):

**Render.com (empfohlen):**
1. Repository auf GitHub pushen/forken
2. Auf [render.com](https://render.com): New Web Service → GitHub-Repo verbinden
3. Render erkennt `render.yaml` automatisch
4. In claude.ai unter Settings → MCP Servers eintragen: `https://your-app.onrender.com/sse`

**Docker:**
```bash
docker build -t swiss-environment-mcp .
docker run -p 8000:8000 swiss-environment-mcp
```

> 💡 *«stdio für den Entwickler-Laptop, SSE für den Browser.»*

---

## Verfügbare Tools

Alle Tools tragen das stabile Namens-Präfix `env_` — eine bewusste
Namespace-Wahl, damit die Tools des Servers erkennbar sind und beim gemeinsamen
Einbinden mehrerer MCP-Server nicht kollidieren. Tool-Definitionen (Name,
Beschreibung, Input-Schema) sind über `tool-snapshot.json` gepinnt; Änderungen
erfordern einen CHANGELOG-Eintrag (siehe CONTRIBUTING).

**Tool-Budget (21 Tools, 7 Cluster) — ausgeschöpft.** Jedes Tool entspricht einer
eigenen Nutzerfrage, nicht einem REST-Endpoint — kein CRUD-/Endpoint-Mapping, und
die Anchor-Queries sind je in einem Call beantwortbar. Die Anzahl liegt über der
Faustregel ≤12, weil der Server bewusst sieben Umweltdomänen abdeckt (Luft,
Wasser, Naturgefahren, Schnee, Jagd, Katalog, Fluglärm), die je ein
Listen-/Detail-Paar oder eine domänenspezifische Aktion brauchen. Weitere
Zusammenlegung wurde geprüft und verworfen: Die `*_stations`/`*_current`-Paare
(NABEL, Hydro, Schnee) bedienen echte unterschiedliche Absichten (Finden vs.
Auslesen einer bekannten Station); ein Zusammenlegen würde die Parameter eines
einzelnen Tools überladen.

**Damit ist die Obergrenze erreicht.** Mit dem Fluglärm-Cluster ist das
Tool-Budget dieses Servers ausgeschöpft: Jede weitere Datenquelle gehört in einen
eigenen `*-mcp`-Server, nicht hierher. Eine nächste Erweiterung würde stattdessen
eine Prüfung auslösen, ob einzelne Listen-Tools zu MCP-Resources migriert werden
sollten.

### 🌬️ Luftqualität / NABEL (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_nabel_stations` | Alle 16 NABEL-Messstationen mit Standorttyp und Kanton auflisten | NABEL / BAFU |
| `env_nabel_current` | Aktuelle Luftqualitätsdaten einer Station (NO₂, O₃, PM10, PM2.5, SO₂, CO) | NABEL / BAFU |
| `env_air_limits_check` | Messwert gegen Schweizer LRV-Grenzwerte und WHO-2021-Richtwerte prüfen | Integriert |

### 💧 Hydrologie (5 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_hydro_stations` | Hydrologische Messstationen nach Gewässer filtern (Kantonsfilter nicht verfügbar — siehe Hinweise) | **LINDAS SPARQL** → hydrodaten.admin.ch (Fallback) |
| `env_hydro_current` | Aktueller Pegel, Abfluss und Wassertemperatur einer Station | **LINDAS SPARQL** → hydrodaten.admin.ch (Fallback) |
| `env_hydro_history` | Historische Stundenwerte (bis 30 Tage) mit Download-Links ⚠️ | hydrodaten.admin.ch |
| `env_flood_warnings` | Aktive Hochwasserwarnungen nach Gefahrenstufe (schweizweit — Kantonsfilter wird nicht angewendet) | **LINDAS SPARQL** |
| `env_bathing_water` | Badegewässerqualität (E.coli, Enterokokken) je Badestelle — Mehrjahres-Zeitreihe | **LINDAS SPARQL** (Data-Cube `ubd0104`) |

### 🏔️ Naturgefahren (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_hazard_overview` | Router: verweist auf die dedizierten Live-Gefahren-Tools + offizielle Portale (kein Netzwerk-Call — die aggregierte `naturgefahren.ch`-API wurde stillgelegt) | lokal |
| `env_hazard_regions` | Router: ordnet einen Gefahrentyp (Hochwasser/Lawine/Waldbrand/Schnee) dem passenden Live-Tool + Portal zu (kein Netzwerk-Call) | lokal |
| `env_wildfire_danger` | Waldbrandgefahren-Index nach Kantonen und Regionen | waldbrandgefahr.ch |

### ❄️ Schnee & Lawinen / SLF (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_snow_stations` | Automatische SLF/IMIS-Schneemessstationen auflisten (nach Kanton) | measurement-api.slf.ch |
| `env_snow_current` | Aktuelle Schneehöhe (HS) und Neuschnee 24 h (HN_1D) je Station, in cm | measurement-api.slf.ch |
| `env_avalanche_bulletin` | Lawinenwarnstufen (EAWS 1–5) je Warnregion, saisonal | aws.slf.ch |

### 🦌 Jagd & Wildtiere (2 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_hunting_species` | Die 36 in der Eidg. Jagdstatistik erfassten Tierarten (mit Codes) auflisten | jagdstatistik.ch (eingebettet) |
| `env_hunting_stats` | Abschuss-/Fallwild-/Bestandszahlen je Tierart, Kanton und Jahr (2015–2024) | jagdstatistik.ch |

### 📊 Umweltdatenkatalog (2 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_bafu_datasets` | BAFU-Datensätze auf opendata.swiss suchen (CKAN-API) | opendata.swiss |
| `env_bafu_dataset_detail` | Vollständige Metadaten und Download-URLs eines Datensatzes | opendata.swiss |

### ✈️ Fluglärm / BAZL-Lärmbelastungskataster (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_noise_aircraft_at` | Fluglärmbelastung an einem **LV95**-Punkt — löst die überlappenden Lärmkurven auf und liefert eine dB-Klammer mit dem höchsten Wert als oberer Schranke | **api3.geo.admin.ch** (BAZL) |
| `env_noise_aircraft_registers` | Welche Flugplätze haben einen publizierten Kataster, mit Gültigkeitsdatum, dB-Bereich und amtlichem Plan (PDF) — das Provenienz-Tool | **api3.geo.admin.ch** (BAZL) |
| `env_noise_limits_check` | Vergleich eines Beurteilungspegels gegen die LSV-Belastungsgrenzwerte (Planungswert / Immissionsgrenzwert / Alarmwert) nach Empfindlichkeitsstufe ES I–IV | eingebaut (SR 814.41, Anhang 5) |

> ⚖️ **Rechtlicher Hinweis — steht in jeder Antwort dieser drei Tools.** Der
> Lärmbelastungskataster ist eine *Orientierungsgrundlage*. Rechtsverbindliche
> Auskünfte zu Bauvorhaben erteilen die zuständige kantonale Fachstelle bzw. das
> BAZL. Diese Tools ersetzen keine Baubewilligungsabklärung.

**Koordinaten müssen LV95 sein** (EPSG:2056, Meter: E ca. 2'480'000–2'840'000,
N ca. 1'070'000–1'300'000). WGS84-Grad wie `8.54 / 47.37` werden **fail-fast**
mit einem Umrechnungshinweis abgewiesen — das ist der häufigste LLM-Fehler bei
Schweizer Geodaten. Umrechnung über swisstopo REFRAME oder `convert_coordinates`
in [swisstopo-mcp](https://github.com/malkreide/swisstopo-mcp).

**Die Kurven sind Linien, keine Flächen.** Der Kataster publiziert
`MultiLineString`-Isolinien; `identify` führt deshalb eine *Näherungsabfrage* im
Suchradius durch, keinen Punkt-in-Fläche-Test. `env_noise_aircraft_at` liefert
darum eine **Klammer** («der Punkt liegt zwischen der 61-dB- und der
62-dB-Kurve») mit dem höchsten Wert als ausgewiesener **oberer Schranke**, nie
einen interpolierten Punktwert. Der Suchradius steht in jeder Antwort; ihn zu
vergrössern überschätzt das Ergebnis (an einem Punkt bei Kloten: 100 m →
61–62 dB, aber 500 m → 58–75 dB, weil die 75-dB-Pistenkurve 1,5 km entfernt liegt).

### Anchor Demo Query

> **«Liegt der geplante Schulhausstandort in einer Fluglärmzone mit Bauauflagen —
> und in welcher dB-Stufe?»**

Cross-Server-Ablauf: Adresse oder EGID über
[swiss-housing-mcp](https://github.com/malkreide/swiss-housing-mcp) auflösen → in
eine LV95-Koordinate umrechnen → `env_noise_aircraft_at(east=…, north=…,
period="day")` → den resultierenden `level_db` an
`env_noise_limits_check(level_db=…, sensitivity_level="II", period="day")` für
die rechtliche Einordnung übergeben.

```
swiss-housing-mcp  →  Adresse / EGID  →  LV95 E/N
                                           ↓
                           env_noise_aircraft_at   → 62 dB (obere Schranke, LBK Zürich, gültig ab 03.07.2015)
                                           ↓
                           env_noise_limits_check  → Immissionsgrenzwert ES II (60 dB) um 2 dB überschritten
```

### Beispiel-Abfragen

| Abfrage | Tool |
|---|---|
| *«Luftqualität an Zürich-Kaserne gerade?»* | `env_nabel_current` |
| *«Überschreitet 45 µg/m³ NO₂ den Schweizer Grenzwert?»* | `env_air_limits_check` |
| *«Aktueller Wasserstand der Limmat in Zürich?»* | `env_hydro_current` |
| *«Ist die Wasserqualität im Strandbad Küsnacht zum Baden unbedenklich?»* | `env_bathing_water` |
| *«Aktive Hochwasserwarnungen in der Schweiz?»* | `env_flood_warnings` |
| *«Naturgefahren-Bulletin für Graubünden?»* | `env_hazard_overview` |
| *«Waldbrandgefahr im Kanton Wallis?»* | `env_wildfire_danger` |
| *«BAFU-Biodiversitätsdatensätze auf opendata.swiss?»* | `env_bafu_datasets` |
| *«Liegt der geplante Schulhausstandort in einer Fluglärmzone — in welcher dB-Stufe?»* | `env_noise_aircraft_at` |
| *«Wie alt ist der Lärmbelastungskataster für den Flughafen Genf?»* | `env_noise_aircraft_registers` |
| *«Überschreiten 62 dB nachts den LSV-Grenzwert in einer ES-II-Wohnzone?»* | `env_noise_limits_check` |

---

## 🛡️ Safety & Limits

| Aspekt | Details |
|--------|---------|
| **Zugriff** | Nur lesend (`readOnlyHint: true`) — der Server kann keine Daten ändern oder löschen |
| **Personendaten** | Keine personenbezogenen Daten — alle Quellen sind aggregierte, öffentliche Umweltmessdaten |
| **Rate Limits** | Eingebaute Obergrenzen pro Abfrage (z.B. max. 30 Tage Hydrologie-Historie, 50 Datensatz-Suchergebnisse) |
| **Timeout** | 30 Sekunden pro API-Aufruf |
| **Authentifizierung** | Keine API-Keys nötig — alle BAFU-Endpunkte sind öffentlich zugänglich |
| **Lizenzen** | BAFU Open Government Data (OGD) — freie Nutzung mit obligatorischer Quellenangabe |
| **Nutzungsbedingungen** | Es gelten die ToS der jeweiligen Datenquellen: [BAFU / opendata.swiss](https://opendata.swiss/de/organization/bafu), [hydrodaten.admin.ch](https://hydrodaten.admin.ch), [naturgefahren.ch](https://naturgefahren.ch), [waldbrandgefahr.ch](https://waldbrandgefahr.ch) |

---

## Architektur

```
┌─────────────────┐     ┌───────────────────────────┐     ┌──────────────────────────┐
│   Claude / KI   │────▶│   Swiss Environment MCP   │────▶│  BAFU / Bundesbehörden   │
│   (MCP Host)    │◀────│   (MCP Server)            │◀────│                          │
└─────────────────┘     │                           │     │  hydrodaten.admin.ch     │
                        │  21 Tools · 3 Resources   │     │  naturgefahren.ch        │
                        │  Stdio | SSE              │     │  waldbrandgefahr.ch      │
                        │                           │     │  opendata.swiss (CKAN)   │
                        │  api_client.py            │     └──────────────────────────┘
                        │  server.py (FastMCP)      │
                        └───────────────────────────┘
```

### Architektur-Notiz — extraktionsfähiges `lindas/`-Modul

Der gesamte LINDAS-SPARQL-Zugriff läuft über das bewusst **extraktionsfähig**
gebaute Modul `src/swiss_environment_mcp/lindas/` mit strikter
Drei-Schichten-Trennung: `client.py` kennt nur SPARQL und HTTP (GET/POST,
45-s-Client-Timeout, `QueryError` mit der MALFORMED-Meldung des Servers,
Retry 2 s/4 s/8 s); `cube.py` kennt das cube.link-Vokabular (zwingender
`observationSet`-Zwei-Phasen-Zugriff, Versions-Deduplizierung über
`schema:expires`, Code→Label-Auflösung, Lizenz-Ermittlung); die Tools rufen
ausschliesslich `cube.py` auf. Das Modul wird nach `lindas-mcp` gehoben,
sobald ein zweiter Server LINDAS nutzt (Kandidat: `wsl-envidat-mcp`).

### Architektur-Entscheid — Live-API für den Fluglärmkataster

Der übrige Server folgt dem **Dump-first**-Standard des Portfolios. Der
Fluglärm-Cluster weicht bewusst ab: `env_noise_aircraft_at` und
`env_noise_aircraft_registers` fragen `api3.geo.admin.ch` bei **jedem Aufruf
live** ab.

Das ist *kein* Grössenargument. Am 2026-07-28 gemessen umfasst der gesamte
Kataster **747 Objekte (~3 MB GeoJSON)** über alle acht Sublayer — er liesse sich
ohne Weiteres spiegeln. Ausschlaggebend sind zwei andere Gründe:

1. **Ein Spiegel würde die Frischezusage entwerten.** Die Kataster werden je
   Flugplatz einzeln und unangekündigt nachgeführt (Gültigkeitsdaten 2009–2024).
   Aus einem Dump gelesen wäre `source_freshness` das `validfrom` zum
   Spiegelzeitpunkt — das Tool würde Provenienz *behaupten*, die es nicht mehr
   hat. Für einen Cluster, dessen drittes Tool genau die Frage «wie alt ist die
   Grundlage» beantwortet, ist das der schlechtestmögliche Fehlermodus.
2. **Die räumliche Abfrage ist der Wert, nicht die Attribute.** Lokal
   ausgewertet bedeutet sie Punkt-zu-Linie-Distanzen über 26'000+ Stützpunkte je
   Layer. Das erfordert entweder **shapely/GEOS** — die erste kompilierte
   Abhängigkeit in einem bewusst binärfreien `pyproject.toml` (Docker-Image,
   Wheel-Matrix und Security-Surface ändern sich alle) — oder eigene
   Distanzmathematik. Letztere wäre machbar, da LV95 eine metrische Projektion
   ist und euklidische Distanz exakt stimmt; dann verantwortete aber *dieser
   Server* die Richtigkeit einer amtlichen Lärmkatasterauskunft statt des
   Bundesamts.

Vollständige Messwerte und Begründung: [`docs/probe-fluglaerm.md`](docs/probe-fluglaerm.md).

### Datenquellen

| Quelle | Daten | Lizenz |
|---|---|---|
| [lindas.admin.ch](https://lindas.admin.ch) | Aktuelle Hydrologie (Pegel, Abfluss, Wassertemperatur) und Badegewässerqualität via SPARQL | BAFU Open-Use / OGD (je Graph/Datensatz deklariert — jede Antwort trägt ein Lizenzfeld) |
| [hydrodaten.admin.ch](https://hydrodaten.admin.ch) | Pegel, Abfluss, Temperaturen (REST-Fallback) | BAFU OGD |
| [naturgefahren.ch](https://naturgefahren.ch) | Naturgefahren-Bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://waldbrandgefahr.ch) | Waldbrandgefahren-Index | BAFU |
| [SLF-Datenservice](https://www.slf.ch/de/services-und-produkte/slf-datenservice/) | Schneehöhe, Neuschnee (IMIS); Lawinenbulletin | SLF (WSL) CC BY 4.0 |
| [jagdstatistik.ch](https://www.jagdstatistik.ch/de/home) | Eidg. Jagdstatistik (Abschuss, Fallwild, Bestand) | BAFU — Quellenangabe erforderlich (keine explizite Lizenz publiziert) |
| [api3.geo.admin.ch](https://api3.geo.admin.ch) | BAZL-Lärmbelastungskataster Fluglärm (`identify`, LV95) | swisstopo / BAZL — freie Nutzung mit Quellenangabe |
| [opendata.swiss](https://opendata.swiss/de/organization/bafu) | BAFU-Datenkatalog (CKAN-API) | OGD |

Alle Daten: öffentlich zugänglich, keine Authentifizierung erforderlich.  
**Quellenangabe erforderlich:** Bei Verwendung der Daten müssen BAFU bzw. SLF (WSL) als Quelle angegeben werden.

---

## Projektstruktur

```
swiss-environment-mcp/
├── src/swiss_environment_mcp/
│   ├── __init__.py          # Paket
│   ├── server.py            # FastMCP-Server: 21 Tools, 3 Resources
│   ├── api_client.py        # HTTP-Client + Egress-Allow-List (SSRF-Schutz)
│   └── logging_setup.py     # structlog -> stderr
├── tests/
│   ├── test_unit.py         # Gemockte Unit-Tests (ohne Netz) — CI-Default
│   ├── test_integration.py  # Live-API-Tests (Marker: live)
│   └── test_20_scenarios.py # Live-Szenarien
├── scripts/tool_snapshot.py # Tool-Definition-Snapshot (Rug-Pull-Schutz)
├── docs/                    # security.md, scaling.md, roadmap.md
├── .github/
│   ├── dependabot.yml       # Monatliche Dependency-/Action-Updates
│   └── workflows/           # ci.yml, security.yml (gitleaks), live-tests.yml, publish.yml
├── Dockerfile               # Multi-Stage, non-root Container
├── render.yaml / Procfile   # Cloud-Deployment
├── tool-snapshot.json       # Committeter Tool-Definition-Snapshot
├── .env.example             # Nicht-geheime Konfig-Vorlage
└── pyproject.toml           # Build-Konfiguration (hatchling)
```

> **Single-Modul-Layout (Begründung, Audit ARCH-011):** Die 21 Tools liegen in
> einer `server.py` statt in einem `tools/`-Paket. Sie sind schlanke, uniforme
> Wrapper über `api_client.py` mit gleichem Input-/Response-Muster — ein gut
> gegliedertes Einzelmodul bleibt navigierbarer als 4 fast identische Dateien.
> Bewusste, dokumentierte Abweichung; eine Aufteilung wird geprüft, sobald die
> Tool-Logik uneinheitlicher wird.

---

## MCP-Protokoll-Version & Wartung

Dieser Server bedient **zwei Protokoll-Aeren** ueber denselben Endpunkt. Die
erste Anfrage einer Verbindung entscheidet, welche gilt; ein spaeterer Anspruch
aus der jeweils anderen Aera wird abgewiesen.

| Aera | Revision | Wer sie erreicht |
|---|---|---|
| `initialize`-Handshake | `2024-11-05` … **`2025-11-25`** | Was heutige Clients sprechen. Der Server antwortet mit der angefragten Revision — oder mit der Obergrenze `2025-11-25`, wenn die Anfrage etwas Neueres verlangt. |
| Pro-Request-Envelope | **`2026-07-28`** | Eine Anfrage mit dem `2026-07-28`-`_meta`-Envelope oeffnet eine moderne Verbindung. |

Beide Revisionen sind in
[`tests/test_protocol_version.py`](tests/test_protocol_version.py) gepinnt und
werden gegen das installierte SDK geprueft; ein Dependabot-Bump von `mcp` kann
also keine der beiden still verschieben. Dieser Server baut keine ASGI-App, durch die sich ein `initialize`
schicken liesse; das Gate sichert deshalb die SDK-Konstanten statt einer
gemessenen Antwort — die schwaechere Form, benannt statt verschwiegen.

Zu beachten: `LATEST_PROTOCOL_VERSION` im SDK ist ein Alias auf die **moderne**
Aera, nicht auf die Handshake-Aera — wer nur dagegen pinnt, laesst genau die
Aera frei wandern, die heutige Clients tatsaechlich aushandeln.

**Update-Politik.** Faellt das Gate, die Konstante nicht blind nachziehen: erst
das Spec-Changelog zwischen den beiden Revisionen lesen, pruefen, ob sich der
Server weiterhin richtig verhaelt, dann Konstante, diesen Abschnitt, `README.md`
und [`CHANGELOG.md`](CHANGELOG.md) gemeinsam bewegen.

- **Tool-Definition-Stabilität (Audit SEC-022):** Jede Änderung an Name,
  Beschreibung oder Parametern eines Tools ändert `tool-snapshot.json`; die CI
  schlägt fehl, bis der Snapshot neu erzeugt und ein `CHANGELOG`-Eintrag +
  Versions-Bump ergänzt sind.
- **Update-Policy:** Dependabot-PRs monatlich prüfen; bei Tool-Definition- oder
  Verhaltensänderung die Version bumpen (semver).

## Lebenszyklus-Phase

Dieser Server ist in **Phase 1 (read-only)** — alle Tools read-only, keine Auth,
keine Seiteneffekte. Phasenmodell und Voraussetzungen für Phase 2 (Write/Auth)
stehen in [`docs/roadmap.md`](docs/roadmap.md). Security-Architektur (SSRF/Egress,
Secret-Management, Lethal-Trifecta-Bewertung): [`docs/security.md`](docs/security.md).
Skalierungs-/Session-Strategie: [`docs/scaling.md`](docs/scaling.md).

---

## Bekannte Einschränkungen

- **Hydrologie via LINDAS**: `env_hydro_current`, `env_hydro_stations` und `env_flood_warnings` fragen den BAFU-LINDAS-SPARQL-Endpoint ab (typisierte Live-Werte: Pegel, Abfluss, Wassertemperatur, Gefahrenstufe). LINDAS enthält **nur aktuelle Werte** (eine Observation pro Station) — **keine** historische Zeitreihe. Siehe [`docs/probe-lindas-hydro.md`](docs/probe-lindas-hydro.md).
- **Historische Hydrologie / `env_hydro_history` (BUG-01 behoben)**: Die alten `hydrodaten.admin.ch/lhg/az/*`-REST-Endpoints (Stunden-CSV, `warnings.json`, Stations-JSON) sind **stillgelegt (404)**. `env_flood_warnings` nutzt neu LINDAS `dangerLevel`. Echte historische Zeitreihen (Tages-/Langzeitmittel — z.B. *Sommer 2024 vs. langjähriges Mittel*) sind **nicht frei per API verfügbar**; sie müssen bei der **BAFU Hydrologischen Abfragezentrale** (abfragezentrale@bafu.admin.ch) bezogen werden. `env_hydro_history` liefert den aktuellsten LINDAS-Wert plus diesen Bezugsweg.
- **Hochwasserwarnungen**: `env_flood_warnings` liest LINDAS `dangerLevel`. Ein Kantonsfilter ist dort nicht verfügbar (LINDAS führt keinen Kantons-Code), die Antwort ist deshalb **immer schweizweit**; ein gesetzter `canton` wird zurückgegeben und als nicht angewendet ausgewiesen — im JSON-Envelope über `match_type: "fuzzy"` plus Hinweis, im Markdown als Warnzeile über der Tabelle. Am wichtigsten ist das, wenn es gar keine Warnungen gibt: «keine aktiven Warnungen» plus ein Kanton in der Anfrage liest sich sonst als kantonale Entwarnung.
- **Messstationen / Kantonsfilter**: `env_hydro_stations` bedient `canton` nicht mehr. Die einzige Quelle mit Kantons-Code — `hydrodaten.admin.ch/lhg/az/json/mobile_stations.json` — ist **stillgelegt (404)**, und LINDAS führt kein Kantons-Attribut. Eine Abfrage mit gesetztem `canton` liefert eine Erklärung statt einer Stationsliste; stattdessen `water_body` nutzen oder die vollständige Liste (233 Stationen) ungefiltert holen.
- **Badegewässerqualität (`env_bathing_water`)**: liest den LINDAS-Data-Cube `foen/ubd01041prod` — den einzigen Hydro-Cube mit echter Mehrjahres-Zeitreihe (Saisonproben seit 2020). Die Daten werden **jährlich nach der Badesaison** nachgeführt (kein Echtzeit-Monitoring); die Erhebung umfasst nur die offiziell gemeldeten Badestellen (viele populäre Badis fehlen). Die Lizenz ist auf Graph-/Datensatz-Ebene deklariert, nicht am Cube — jede Antwort trägt deshalb ein explizites Lizenzfeld, mit ehrlichem «nicht deklariert»-Hinweis, wo keines existiert. Siehe [`docs/probe-lindas-hydro.md`](docs/probe-lindas-hydro.md) (Nachtrag N1–N7).
- **Kein Grundwasser in LINDAS**: am 2026-07-24 per mehrsprachiger Cube-Suche verifiziert — LINDAS enthält **keinen Grundwasser-Cube** (NAQUA-Grundwasserstände sind nicht via SPARQL verfügbar).
- **NABEL**: Nur Nahzeit-Daten; keine historischen Zeitreihen über diesen Server.
- **Naturgefahren (`env_hazard_overview` / `env_hazard_regions`)**: Die früheren `naturgefahren.ch/api/v1/warnings/*`-REST-Endpoints sind **stillgelegt (2026)** und — am 2026-07-26 verifiziert — es existiert **kein stabiler, dokumentierter öffentlicher JSON-Feed** für die aggregierten Warnungen (MeteoSchweiz-OGD/STAC, opendata.swiss und die undokumentierte App-API wurden alle geprüft). Statt eines fragilen Scrapings sind beide Tools jetzt **netzwerkfreie Orientierungs-/Routing-Tools**: Sie verweisen deterministisch auf die dedizierten Live-Tools dieses Servers (Hochwasser→`env_flood_warnings`, Lawine→`env_avalanche_bulletin`, Waldbrand→`env_wildfire_danger`, Schnee→`env_snow_current`) und die offiziellen Portale. Aggregierte **Wetterwarnungen** (Sturm/Gewitter/Hitze) sind Domäne von MeteoSchweiz und gehören in `meteoswiss-mcp`. Siehe [`docs/probe-naturgefahren-hazards.md`](docs/probe-naturgefahren-hazards.md).
- **Waldbrandgefahr (`env_wildfire_danger`)**: `waldbrandgefahr.ch` hat 2026 seine REST-API durch eine Rails/React-App ersetzt; es gibt **keinen stabilen JSON-Endpoint** mehr. Die aktuellen Gefahrenstufen werden über einen **zweistufigen, HTML-getragenen Vertrag** gelesen: Die `data-react-props` der Startseite liefern eine *signierte* ActiveStorage-Blob-URL (`warnMapJsonPath`) plus das Kanton-Mapping, die dann abgerufen wird. Ein Schema-Guard degradiert graceful, falls sich die Struktur ändert. Ohne Filter werden die Resultate auf 40 Regionen begrenzt (höchste Stufen zuerst); mit `canton` filtern für die vollständige Kantonsliste. Siehe [`docs/probe-naturgefahren-waldbrand.md`](docs/probe-naturgefahren-waldbrand.md).
- **Jagdstatistik (`env_hunting_stats`)**: Das `jagdstatistik.ch`-Backend ist **undokumentiert** (content-negotiierter Web-App-Endpoint). Ein Schema-Guard fängt Strukturänderungen sauber ab. Tierart-/Kanton-/Datentyp-Codes sind eingebettet (Stand 2026-07-19), die Zahlen werden live abgefragt (2015–2024). **Lizenz (recherchiert 2026-07-19):** Die Daten gehören dem **BAFU** (aus kantonalen Stellen zusammengetragen; Technik durch Wildtier Schweiz) und sind **nicht** als lizenzierter Datensatz auf opendata.swiss publiziert; **auf der Quelle ist keine explizite Lizenz ausgewiesen**. Antworten enthalten daher die Quellenangabe zum BAFU; eine formelle Lizenzbestätigung des BAFU steht noch aus. Siehe [`docs/probe-jagdstatistik.md`](docs/probe-jagdstatistik.md).
- **Strassen- und Bahnlärm sind out of scope (`ch.bafu.laerm-*`, `ch.bav.laermbelastung-*`)**: am 2026-07-28 verifiziert. Die BAFU-Strassenlärm-Layer `ch.bafu.laerm-strassenlaerm_tag` / `_nacht` quittieren dieselbe `identify`-Anfrage mit **HTTP 400** — es sind reine Rasterdienste (`type: wmts`, `tooltip: false`) ohne Attributabfrage, eine Punktabfrage ist damit technisch unmöglich. Beim Bahnlärm ist es anders: `ch.bav.laermbelastung-eisenbahn_*` antwortet **mit HTTP 200** und echten Attributen (`de_es`, `de_pointofdetermination`) — Bahnlärm ist also *abfragbar* und trotzdem bewusst **nicht angebunden**: das Tool-Budget ist bei 21 ausgeschöpft, und Bahnlärm bräuchte ein eigenes Perioden-/Attributmodell. Merksatz: *Fluglärm hat Linien, Strassenlärm hat nur Pixel* — Bahnlärm hätte Daten, ist aber eine bewusste Auslassung. Siehe [`docs/probe-fluglaerm.md`](docs/probe-fluglaerm.md).
- **Fluglärm ist ein Stichtagskataster, kein Live-Dienst (`env_noise_*`)**: `validfrom` reicht von **01.03.2009** (CDB Genève) bis **16.04.2024** (LBK St. Gallen-Altenrhein), und jeder Flugplatz wird einzeln und unangekündigt nachgeführt. `source_freshness` behauptet deshalb nie «live» — es trägt das `validfrom` des tatsächlich gefundenen Registers. Die Abdeckung beschränkt sich auf die Umgebung von Flugplätzen; für den grössten Teil der Schweiz existiert kein Kataster, was das Tool ausdrücklich meldet statt eine leere Liste zurückzugeben. Null Treffer bei kleinem Radius ist **zweideutig** (ausserhalb jedes Katasters *oder* innerhalb der innersten Kurve — auf der Piste Kloten sieht beides bei 100 m identisch aus); das Tool fasst deshalb einmal mit Fernradius nach und unterscheidet `no_cadastre` von `wide_area_only`.
- **Die LSV-Grenzwertprüfung schliesst Militärflugplätze aus**: Anhang 5 der Lärmschutz-Verordnung gilt ausdrücklich für *zivile* Flugplätze. Für Militärflugplätze ist Anhang 8 einschlägig; er wurde nicht verifiziert, weshalb `env_noise_limits_check` die Prüfung für `period="military"` **verweigert** und auf die richtige Grundlage verweist, statt eine plausibel aussehende falsche Tabelle anzuwenden.

### Zuständigkeitsmatrix — Gewässer, Schnee & Niederschlag (Abgrenzung zu `meteoswiss-mcp`)

Damit sich **Gewässer-, Schnee- und Niederschlagsdaten** im Portfolio nicht
duplizieren, sind die Zuständigkeiten wie folgt aufgeteilt. `meteoswiss-mcp`
verantwortet den atmosphärischen Niederschlag und das Wetter;
`swiss-environment-mcp` verantwortet die Oberflächengewässer (BAFU-Domäne:
Abfluss, Pegel, Wassertemperatur, Badegewässerqualität), Schnee am Boden und
Lawinengefahr. Gegen die konkreten LINDAS-Cube-Dimensionen geprüft (2026-07-24):
**keine Überschneidung der Messgrössen**.

| Grösse | swiss-environment-mcp (BAFU / SLF) | meteoswiss-mcp (MeteoSchweiz) |
|---|---|---|
| Abfluss (m³/s) | ✅ `env_hydro_current` (LINDAS `hydro/river`) | ❌ |
| Wasserstand / Pegel (m ü. M.) | ✅ `env_hydro_current` (LINDAS `hydro/river` + `lake`) | ❌ |
| Wassertemperatur (°C) | ✅ `env_hydro_current` | ❌ (misst Lufttemperatur) |
| Badegewässerqualität (E.coli u. a.) | ✅ `env_bathing_water` (LINDAS `ubd0104`) | ❌ |
| Schneehöhe am Boden (`HS`) | ✅ `env_snow_current` (SLF IMIS) | ❌ |
| Neuschnee 24 h (`HN_1D`) | ✅ `env_snow_current` (SLF IMIS) | ❌ |
| Lawinenwarnstufe | ✅ `env_avalanche_bulletin` (SLF, EAWS 1–5) | ❌ |
| Schneefall als aktuelle Wetterlage | ❌ | ✅ `meteo_current` / `meteo_forecast` (Wettercode) |
| Niederschlagsmenge (mm): Messnetz, Prognose, Klimanormwerte | ❌ | ✅ `meteo_current` / `meteo_forecast` / `meteo_climate_normals` |
| Niederschlag an SLF-IMIS-Bergstationen | ✅ nur als Schneedecken-Kontext, **kein eigenes Niederschlags-Tool** | (MeteoSchweiz-Messnetz) |
| Wetterwarnungen (Sturm, Gewitter, Hitze) | ❌ | ✅ `meteo_warnings` |
| Naturgefahren-Warnungen (Hochwasser, Lawine, Waldbrand) | ✅ `env_flood_warnings`, `env_hazard_*`, `env_wildfire_danger` | ❌ |

**Regel:** Alles **im und am Gewässer** (Abfluss, Pegel, Wassertemperatur,
Badegewässerqualität), Schnee **am Boden** und **Lawinengefahr** gehören zu
`swiss-environment-mcp` (BAFU/SLF); **atmosphärischer Niederschlag**
(Regen/Schneefall als mm) sowie Wetter, Prognose, Warnungen und Klimanormwerte
gehören zu `meteoswiss-mcp`. Der IMIS-Niederschlagssensor des SLF (`RR_10MIN_SUM`)
wird bewusst **nicht** als Tool angebunden — damit keine Duplikation mit
MeteoSchweiz. Die Schnee-/Lawinen-Tools sind live (siehe
[`docs/probe-slf.md`](docs/probe-slf.md)).
*TODO (hier out of scope): Diese Matrix auch im README von `meteoswiss-mcp`
spiegeln — jenes Repository ist nicht Teil dieser Änderung.*

---

## Tests

```bash
# Unit-Tests (kein Netzwerk erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Integrationstests (erfordern live BAFU-APIs)
PYTHONPATH=src pytest tests/ -m "live"

# Linting
ruff check src/
```

---

## Beitragen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) (Englisch) · [CONTRIBUTING.de.md](CONTRIBUTING.de.md) (Deutsch)

---

## Sicherheit

Sicherheitsrichtlinie und Sicherheitslage: [SECURITY.md](SECURITY.md) (Englisch) · [SECURITY.de.md](SECURITY.de.md) (Deutsch).
Vollständige Sicherheitsarchitektur: [`docs/security.md`](docs/security.md).

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Lizenz

MIT-Lizenz – siehe [LICENSE](LICENSE)

Die Quelldaten unterliegen den BAFU-Nutzungsbedingungen. Die Quellenangabe des BAFU ist bei der Verwendung ihrer Daten Pflicht.

---

## Autor

Hayal Oezkan · [github.com/malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Daten:** [BAFU / Bundesamt für Umwelt](https://www.bafu.admin.ch) · [hydrodaten.admin.ch](https://hydrodaten.admin.ch) · [naturgefahren.ch](https://naturgefahren.ch) · [opendata.swiss](https://opendata.swiss/de/organization/bafu)
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Verwandt:**

| Server | Beschreibung |
|---|---|
| [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) | Stadt Zürich Open Data (OSTLUFT Luftqualität, Wetter, Parking, Geodaten) |
| [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) | OJP 2.0 Reiseplanung, SIRI-SX Störungen |
| [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) | GBFS Shared Mobility, EV-Ladestationen, DATEX II Verkehr |
| [swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp) | BFS STAT-TAB – 682 Statistik-Datensätze |

**Synergiebeispiel:** *«Wie war die Luftqualität beim Schulhaus Leutschenbach heute – und liegt sie über dem nationalen NABEL-Durchschnitt?»*  
→ `zurich-opendata-mcp` (OSTLUFT, lokal) + `swiss-environment-mcp` (NABEL, national)

- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
