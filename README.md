# 🌿 Swiss Environment MCP

[🇬🇧 English](README_EN.md) | 🇩🇪 Deutsch

**MCP-Server für Schweizer Umweltdaten des BAFU** – Luft, Wasser, Naturgefahren und Umweltindikatoren.

Ermöglicht KI-Assistenten wie Claude, ChatGPT und anderen MCP-kompatiblen Systemen den direkten Zugriff auf Echtzeit-Umweltdaten der Schweizer Bundesbehörden.

[![CI](https://github.com/malkreide/swiss-environment-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-environment-mcp/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![MCP](https://img.shields.io/badge/MCP-kompatibel-green.svg)](https://modelcontextprotocol.io)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](LICENSE)

---

## 🗺️ Überblick

```
swiss-environment-mcp/
├── src/swiss_environment_mcp/
│   ├── __init__.py          # Paket
│   ├── server.py            # MCP-Server: 12 Tools, 3 Resources
│   └── api_client.py        # HTTP-Client für 4 BAFU-Datenquellen
├── tests/
│   └── test_integration.py  # Integrationstests
├── .github/workflows/ci.yml # GitHub Actions CI (Python 3.11–3.13)
├── pyproject.toml
├── README.md / README_EN.md
├── CHANGELOG.md
├── Dockerfile
├── Procfile / render.yaml   # Render.com-Deployment
└── claude_desktop_config.json
```

---

## 🧰 Tools (12)

### 🌬️ Luft / NABEL (3 Tools)
| Tool | Beschreibung |
|------|-------------|
| `env_nabel_stations` | 16 NABEL-Messstationen mit Standorttyp und Kanton auflisten |
| `env_nabel_current` | Aktuelle Luftqualitätsdaten einer NABEL-Station (NO₂, O₃, PM10, PM2.5, SO₂, CO) |
| `env_air_limits_check` | Messwert gegen Schweizer LRV-Grenzwerte und WHO 2021-Richtwerte prüfen |

### 💧 Wasser / Hydrologie (4 Tools)
| Tool | Beschreibung |
|------|-------------|
| `env_hydro_stations` | Hydrologische Messstationen filtern (Kanton, Gewässer) |
| `env_hydro_current` | Aktuelle Pegel, Abfluss und Wassertemperatur einer Messstation |
| `env_hydro_history` | Historische Stundenwerte (bis 30 Tage) mit Download-Links |
| `env_flood_warnings` | Aktive Hochwasserwarnungen nach Gefahrenstufe und Kanton |

### 🏔️ Naturgefahren (3 Tools)
| Tool | Beschreibung |
|------|-------------|
| `env_hazard_overview` | Aktuelles Naturgefahren-Bulletin (SLF/BAFU) in DE/FR/IT/EN |
| `env_hazard_regions` | Regionsspezifische Warnungen (Hochwasser, Lawinen, Steinschlag) |
| `env_wildfire_danger` | Waldbrandgefahren-Index nach Kantonen und Regionen |

### 📊 Umweltdatenkatalog (2 Tools)
| Tool | Beschreibung |
|------|-------------|
| `env_bafu_datasets` | BAFU-Datensätze auf opendata.swiss suchen (CKAN-API) |
| `env_bafu_dataset_detail` | Vollständige Metadaten und Download-URLs eines Datensatzes |

---

## ⚡ Schnellstart

### Option 1: uvx (empfohlen, keine Installation nötig)

```bash
uvx swiss-environment-mcp
```

### Option 2: pip

```bash
pip install swiss-environment-mcp
python -m swiss_environment_mcp.server
```

### Option 3: Entwicklungsmodus

```bash
git clone https://github.com/malkreide/swiss-environment-mcp.git
cd swiss-environment-mcp
pip install -e ".[dev]"
python -m swiss_environment_mcp.server
```

---

## 🖥️ Claude Desktop Konfiguration

Datei: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)  
Datei: `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

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

Nach dem Speichern Claude Desktop neu starten.

---

## 💬 Beispiel-Anfragen

Nach der Konfiguration können folgende Fragen direkt gestellt werden:

- «Wie ist die Luftqualität an der NABEL-Station Zürich-Kaserne?»
- «Überschreitet ein NO₂-Wert von 45 µg/m³ den Schweizer Grenzwert?»
- «Welche Hochwasserwarnungen sind aktuell in der Schweiz aktiv?»
- «Wie ist der aktuelle Wasserstand der Limmat in Zürich?»
- «Wie hoch ist die Waldbrandgefahr im Kanton Wallis gerade?»
- «Zeige mir alle BAFU-Datensätze zur Biodiversität auf opendata.swiss»
- «Was sagt das aktuelle Naturgefahren-Bulletin für Graubünden?»

---

## 🔗 Datenquellen

| Quelle | Daten | Lizenz |
|--------|-------|--------|
| [hydrodaten.admin.ch](https://www.hydrodaten.admin.ch) | Pegel, Abfluss, Temperatur (10-Min-Intervall) | BAFU OGD |
| [naturgefahren.ch](https://www.naturgefahren.ch) | Naturgefahren-Bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://www.waldbrandgefahr.ch) | Waldbrandgefahren-Index | BAFU |
| [opendata.swiss](https://opendata.swiss/de/organization/bafu) | BAFU-Datenkatalog (CKAN-API) | OGD |

Alle Daten: öffentlich zugänglich, keine Authentifizierung erforderlich.

---

## 🏗️ Verwandte MCP-Server

Dieser Server ergänzt das Schweizer Open-Data-MCP-Portfolio:

| Server | Beschreibung |
|--------|-------------|
| [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) | Stadt Zürich Open Data (OSTLUFT Luftqualität, Wetter, Parking, Geodaten) |
| [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) | OJP 2.0 Reiseplanung, SIRI-SX Störungen |
| [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) | GBFS Shared Mobility, EV-Ladestationen, DATEX II Verkehr |
| [swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp) | BFS STAT-TAB (682 Datensätze) |

**Synergiebeispiel:** *«Wie war die Luftqualität beim Schulhaus Leutschenbach heute – und liegt sie über dem nationalen NABEL-Durchschnitt?»*  
→ `zurich-opendata-mcp` (OSTLUFT, lokal) + `swiss-environment-mcp` (NABEL, national)

---

## 🧪 Tests

```bash
# Alle Tests (inkl. Live-API)
python tests/test_integration.py

# Nur Offline-Tests
SKIP_LIVE_TESTS=1 python tests/test_integration.py

# Linting
ruff check src/
```

---

## 📄 Lizenz

[MIT](LICENSE) – Quelldaten unterliegen den BAFU-Nutzungsbedingungen.

**Quellenangabe erforderlich:** Bei Verwendung der BAFU-Daten muss das BAFU als Quelle angegeben werden.
