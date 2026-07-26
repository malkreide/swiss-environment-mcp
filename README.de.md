[🇬🇧 English Version](README.md)

> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# 🌿 swiss-environment-mcp

![Version](https://img.shields.io/badge/version-0.4.0-blue)
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
- 🚨 **Hochwasserwarnungen** – aktive Warnungen nach Gefahrenstufe und Kanton
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

**Tool-Budget (18 Tools, 6 Cluster).** Jedes Tool entspricht einer eigenen
Nutzerfrage, nicht einem REST-Endpoint — kein CRUD-/Endpoint-Mapping, und die
Anchor-Queries sind je in einem Call beantwortbar. Die Anzahl liegt über der
Faustregel ≤12, weil der Server bewusst sechs Umweltdomänen abdeckt (Luft,
Wasser, Naturgefahren, Schnee, Jagd, Katalog), die je ein Listen-/Detail-Paar
oder eine domänenspezifische Aktion brauchen. Weitere Zusammenlegung wurde
geprüft und verworfen: Die `*_stations`/`*_current`-Paare (NABEL, Hydro, Schnee)
bedienen echte unterschiedliche Absichten (Finden vs. Auslesen einer bekannten
Station); ein Zusammenlegen würde die Parameter eines einzelnen Tools
überladen. Eine siebte Domäne würde eine Prüfung auslösen, ob einzelne
Listen-Tools stattdessen zu MCP-Resources migriert werden sollten.

### 🌬️ Luftqualität / NABEL (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_nabel_stations` | Alle 16 NABEL-Messstationen mit Standorttyp und Kanton auflisten | NABEL / BAFU |
| `env_nabel_current` | Aktuelle Luftqualitätsdaten einer Station (NO₂, O₃, PM10, PM2.5, SO₂, CO) | NABEL / BAFU |
| `env_air_limits_check` | Messwert gegen Schweizer LRV-Grenzwerte und WHO-2021-Richtwerte prüfen | Integriert |

### 💧 Hydrologie (5 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_hydro_stations` | Hydrologische Messstationen nach Kanton oder Gewässer filtern | **LINDAS SPARQL** → hydrodaten.admin.ch (Fallback) |
| `env_hydro_current` | Aktueller Pegel, Abfluss und Wassertemperatur einer Station | **LINDAS SPARQL** → hydrodaten.admin.ch (Fallback) |
| `env_hydro_history` | Historische Stundenwerte (bis 30 Tage) mit Download-Links ⚠️ | hydrodaten.admin.ch |
| `env_flood_warnings` | Aktive Hochwasserwarnungen nach Gefahrenstufe und Kanton | hydrodaten.admin.ch |
| `env_bathing_water` | Badegewässerqualität (E.coli, Enterokokken) je Badestelle — Mehrjahres-Zeitreihe | **LINDAS SPARQL** (Data-Cube `ubd0104`) |

### 🏔️ Naturgefahren (3 Tools)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `env_hazard_overview` | Aktuelles Naturgefahren-Bulletin (SLF/BAFU) auf DE/FR/IT/EN | naturgefahren.ch |
| `env_hazard_regions` | Regionsspezifische Warnungen (Hochwasser, Lawinen, Steinschlag) | naturgefahren.ch |
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
                        │  18 Tools · 3 Resources   │     │  naturgefahren.ch        │
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

### Datenquellen

| Quelle | Daten | Lizenz |
|---|---|---|
| [lindas.admin.ch](https://lindas.admin.ch) | Aktuelle Hydrologie (Pegel, Abfluss, Wassertemperatur) und Badegewässerqualität via SPARQL | BAFU Open-Use / OGD (je Graph/Datensatz deklariert — jede Antwort trägt ein Lizenzfeld) |
| [hydrodaten.admin.ch](https://hydrodaten.admin.ch) | Pegel, Abfluss, Temperaturen (REST-Fallback) | BAFU OGD |
| [naturgefahren.ch](https://naturgefahren.ch) | Naturgefahren-Bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://waldbrandgefahr.ch) | Waldbrandgefahren-Index | BAFU |
| [SLF-Datenservice](https://www.slf.ch/de/services-und-produkte/slf-datenservice/) | Schneehöhe, Neuschnee (IMIS); Lawinenbulletin | SLF (WSL) CC BY 4.0 |
| [jagdstatistik.ch](https://www.jagdstatistik.ch/de/home) | Eidg. Jagdstatistik (Abschuss, Fallwild, Bestand) | BAFU — Quellenangabe erforderlich (keine explizite Lizenz publiziert) |
| [opendata.swiss](https://opendata.swiss/de/organization/bafu) | BAFU-Datenkatalog (CKAN-API) | OGD |

Alle Daten: öffentlich zugänglich, keine Authentifizierung erforderlich.  
**Quellenangabe erforderlich:** Bei Verwendung der Daten müssen BAFU bzw. SLF (WSL) als Quelle angegeben werden.

---

## Projektstruktur

```
swiss-environment-mcp/
├── src/swiss_environment_mcp/
│   ├── __init__.py          # Paket
│   ├── server.py            # FastMCP-Server: 18 Tools, 3 Resources
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

> **Single-Modul-Layout (Begründung, Audit ARCH-011):** Die 18 Tools liegen in
> einer `server.py` statt in einem `tools/`-Paket. Sie sind schlanke, uniforme
> Wrapper über `api_client.py` mit gleichem Input-/Response-Muster — ein gut
> gegliedertes Einzelmodul bleibt navigierbarer als 4 fast identische Dateien.
> Bewusste, dokumentierte Abweichung; eine Aufteilung wird geprüft, sobald die
> Tool-Logik uneinheitlicher wird.

---

## MCP-Protokoll-Version & Wartung

- **MCP-Protokoll:** wird beim `initialize` ausgehandelt und vom gepinnten
  MCP-SDK (`mcp[cli]`) verwaltet. Die SDK-Version ist der kanonische Pin;
  SDK-/Protokoll-Updates kommen via Dependabot-PRs (`.github/dependabot.yml`, monatlich).
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
- **Hochwasserwarnungen**: `env_flood_warnings` liest LINDAS `dangerLevel`; ein Kantonsfilter ist dort nicht verfügbar (LINDAS führt keinen Kanton-Code) und wird gemeldet, aber nicht angewendet.
- **Badegewässerqualität (`env_bathing_water`)**: liest den LINDAS-Data-Cube `foen/ubd01041prod` — den einzigen Hydro-Cube mit echter Mehrjahres-Zeitreihe (Saisonproben seit 2020). Die Daten werden **jährlich nach der Badesaison** nachgeführt (kein Echtzeit-Monitoring); die Erhebung umfasst nur die offiziell gemeldeten Badestellen (viele populäre Badis fehlen). Die Lizenz ist auf Graph-/Datensatz-Ebene deklariert, nicht am Cube — jede Antwort trägt deshalb ein explizites Lizenzfeld, mit ehrlichem «nicht deklariert»-Hinweis, wo keines existiert. Siehe [`docs/probe-lindas-hydro.md`](docs/probe-lindas-hydro.md) (Nachtrag N1–N7).
- **Kein Grundwasser in LINDAS**: am 2026-07-24 per mehrsprachiger Cube-Suche verifiziert — LINDAS enthält **keinen Grundwasser-Cube** (NAQUA-Grundwasserstände sind nicht via SPARQL verfügbar).
- **NABEL**: Nur Nahzeit-Daten; keine historischen Zeitreihen über diesen Server.
- **Naturgefahren (`env_hazard_overview` / `env_hazard_regions`)**: Die früheren `naturgefahren.ch/api/v1/warnings/*`-REST-Endpoints sind **stillgelegt (2026, HTTP 301→404)**, ohne Drop-in-Ersatz — die Seite exponiert kein öffentliches Warnungs-JSON mehr. Beide Tools **degradieren daher graceful auf kuratierte Direktlinks** zur Warnplattform und liefern aktuell keine strukturierten Live-Warndaten. Die autoritative maschinenlesbare Quelle ist **MeteoSchweiz**, was sich mit `meteoswiss-mcp` (Wetterwarnungen) überschneidet — ein Repointing dorthin ist als portfolio-übergreifender Follow-up vermerkt. Siehe [`docs/probe-naturgefahren-waldbrand.md`](docs/probe-naturgefahren-waldbrand.md).
- **Waldbrandgefahr (`env_wildfire_danger`)**: `waldbrandgefahr.ch` hat 2026 seine REST-API durch eine Rails/React-App ersetzt; es gibt **keinen stabilen JSON-Endpoint** mehr. Die aktuellen Gefahrenstufen werden über einen **zweistufigen, HTML-getragenen Vertrag** gelesen: Die `data-react-props` der Startseite liefern eine *signierte* ActiveStorage-Blob-URL (`warnMapJsonPath`) plus das Kanton-Mapping, die dann abgerufen wird. Ein Schema-Guard degradiert graceful, falls sich die Struktur ändert. Ohne Filter werden die Resultate auf 40 Regionen begrenzt (höchste Stufen zuerst); mit `canton` filtern für die vollständige Kantonsliste. Siehe [`docs/probe-naturgefahren-waldbrand.md`](docs/probe-naturgefahren-waldbrand.md).
- **Jagdstatistik (`env_hunting_stats`)**: Das `jagdstatistik.ch`-Backend ist **undokumentiert** (content-negotiierter Web-App-Endpoint). Ein Schema-Guard fängt Strukturänderungen sauber ab. Tierart-/Kanton-/Datentyp-Codes sind eingebettet (Stand 2026-07-19), die Zahlen werden live abgefragt (2015–2024). **Lizenz (recherchiert 2026-07-19):** Die Daten gehören dem **BAFU** (aus kantonalen Stellen zusammengetragen; Technik durch Wildtier Schweiz) und sind **nicht** als lizenzierter Datensatz auf opendata.swiss publiziert; **auf der Quelle ist keine explizite Lizenz ausgewiesen**. Antworten enthalten daher die Quellenangabe zum BAFU; eine formelle Lizenzbestätigung des BAFU steht noch aus. Siehe [`docs/probe-jagdstatistik.md`](docs/probe-jagdstatistik.md).

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
