> 🇨🇭 **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# 🌿 swiss-environment-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![CI](https://github.com/malkreide/swiss-environment-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-environment-mcp/actions)
[![Data Source](https://img.shields.io/badge/Data-BAFU%20%2F%20opendata.swiss-green)](https://opendata.swiss/en/organization/bafu)

> MCP server connecting AI models to Swiss environmental data from BAFU – air quality, hydrology, natural hazards, wildfire danger and open environmental datasets.

[🇩🇪 Deutsche Version](README.de.md)

---

## Overview

**swiss-environment-mcp** gives AI assistants like Claude direct access to real-time environmental data from Swiss federal authorities – no API keys required. Air quality readings from the national NABEL monitoring network, hydrological gauging stations, natural hazard bulletins, and the full BAFU dataset catalogue are all accessible through a single standardised MCP interface.

The server covers four thematic clusters: air quality (NABEL), hydrology, natural hazards, and the BAFU open data catalogue. Each cluster maps to a group of purpose-built tools that translate raw agency data into clean JSON responses.

**Anchor demo query:** *"What is the current air quality at the NABEL station Zürich-Kaserne – and does it comply with WHO 2021 guidelines?"*

---

## Features

- 🌬️ **Air quality monitoring** – 16 NABEL stations, NO₂/O₃/PM10/PM2.5/SO₂/CO, Swiss LRV + WHO 2021 limit checks
- 💧 **Hydrology** – water levels, flow rates, temperatures across Swiss gauging stations
- 🚨 **Flood warnings** – active alerts filtered by danger level and canton
- 🏔️ **Natural hazard bulletin** – SLF/BAFU bulletin in DE/FR/IT/EN, region-specific warnings
- 🔥 **Wildfire danger** – canton- and region-level fire danger index
- 📦 **BAFU open data catalogue** – search and retrieve environmental datasets via CKAN
- 🔑 **No authentication required** – all data sources are publicly accessible
- ☁️ **Dual transport** – stdio for Claude Desktop, Streamable HTTP/SSE for cloud deployment

---

## Prerequisites

- Python 3.11+
- No API keys needed – all endpoints are publicly accessible without authentication

---

## Installation

```bash
# Clone the repository
git clone https://github.com/malkreide/swiss-environment-mcp.git
cd swiss-environment-mcp

# Install
pip install -e .
```

Or with `uvx` (no permanent installation):

```bash
uvx swiss-environment-mcp
```

Or via pip:

```bash
pip install swiss-environment-mcp
```

---

## Quickstart

```bash
# Start the server (stdio mode for Claude Desktop)
swiss-environment-mcp
```

Try it immediately in Claude Desktop:

> *"What is the current air quality at NABEL station Zürich-Kaserne?"*
> *"Are there any active flood warnings in Switzerland right now?"*
> *"What is the wildfire danger level in Canton Valais?"*

---

## Configuration

### Claude Desktop

**Minimal (recommended):**

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

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

After saving, restart Claude Desktop completely.

### Cloud Deployment (SSE for browser access)

For use via **claude.ai in the browser** (e.g. on managed workstations without local software):

**Render.com (recommended):**
1. Push/fork the repository to GitHub
2. On [render.com](https://render.com): New Web Service → connect GitHub repo
3. Render detects `render.yaml` automatically
4. In claude.ai under Settings → MCP Servers, add: `https://your-app.onrender.com/sse`

**Docker:**
```bash
docker build -t swiss-environment-mcp .
docker run -p 8000:8000 swiss-environment-mcp
```

> 💡 *"stdio for the developer laptop, SSE for the browser."*

---

## Available Tools

### 🌬️ Air Quality / NABEL (3 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_nabel_stations` | List all 16 NABEL monitoring stations with location type and canton | NABEL / BAFU |
| `env_nabel_current` | Current air quality data for a station (NO₂, O₃, PM10, PM2.5, SO₂, CO) | NABEL / BAFU |
| `env_air_limits_check` | Compare a measurement against Swiss LRV limits and WHO 2021 guidelines | Built-in |

### 💧 Hydrology (4 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_hydro_stations` | Filter hydrological gauging stations by canton or water body | hydrodaten.admin.ch |
| `env_hydro_current` | Current water level, flow rate and temperature at a station | hydrodaten.admin.ch |
| `env_hydro_history` | Historical hourly values (up to 30 days) with download links ⚠️ | hydrodaten.admin.ch |
| `env_flood_warnings` | Active flood warnings filtered by danger level and canton | hydrodaten.admin.ch |

### 🏔️ Natural Hazards (3 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_hazard_overview` | Current natural hazard bulletin (SLF/BAFU) in DE/FR/IT/EN | naturgefahren.ch |
| `env_hazard_regions` | Region-specific warnings (floods, avalanches, rockfall) | naturgefahren.ch |
| `env_wildfire_danger` | Wildfire danger index by canton and region | waldbrandgefahr.ch |

### 📊 Environmental Data Catalogue (2 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_bafu_datasets` | Search BAFU datasets on opendata.swiss (CKAN API) | opendata.swiss |
| `env_bafu_dataset_detail` | Full metadata and download URLs for a specific dataset | opendata.swiss |

### Example Use Cases

| Query | Tool |
|---|---|
| *"Air quality at Zürich-Kaserne right now?"* | `env_nabel_current` |
| *"Does 45 µg/m³ NO₂ exceed the Swiss limit?"* | `env_air_limits_check` |
| *"Current water level of the Limmat in Zurich?"* | `env_hydro_current` |
| *"Active flood warnings in Switzerland?"* | `env_flood_warnings` |
| *"Natural hazard bulletin for Graubünden?"* | `env_hazard_overview` |
| *"Wildfire danger in Canton Valais?"* | `env_wildfire_danger` |
| *"BAFU biodiversity datasets on opendata.swiss?"* | `env_bafu_datasets` |

---

## Architecture

```
┌─────────────────┐     ┌───────────────────────────┐     ┌──────────────────────────┐
│   Claude / AI   │────▶│   Swiss Environment MCP   │────▶│  BAFU / Swiss Agencies   │
│   (MCP Host)    │◀────│   (MCP Server)            │◀────│                          │
└─────────────────┘     │                           │     │  hydrodaten.admin.ch     │
                        │  12 Tools · 3 Resources   │     │  naturgefahren.ch        │
                        │  Stdio | SSE              │     │  waldbrandgefahr.ch      │
                        │                           │     │  opendata.swiss (CKAN)   │
                        │  api_client.py            │     └──────────────────────────┘
                        │  server.py (FastMCP)      │
                        └───────────────────────────┘
```

### Data Sources

| Source | Data | Licence |
|---|---|---|
| [hydrodaten.admin.ch](https://hydrodaten.admin.ch) | Water levels, flow rates, temperatures (10-min intervals) | BAFU OGD |
| [naturgefahren.ch](https://naturgefahren.ch) | Natural hazard bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://waldbrandgefahr.ch) | Wildfire danger index | BAFU |
| [opendata.swiss](https://opendata.swiss/en/organization/bafu) | BAFU data catalogue (CKAN API) | OGD |

All data: publicly accessible, no authentication required.  
**Attribution required:** BAFU must be cited as the source when using their data.

---

## Project Structure

```
swiss-environment-mcp/
├── src/swiss_environment_mcp/
│   ├── __init__.py          # Package
│   ├── server.py            # FastMCP server: 12 tools, 3 resources
│   └── api_client.py        # HTTP client for 4 BAFU data sources
├── tests/
│   └── test_integration.py  # Integration tests
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI (Python 3.11–3.13)
├── Dockerfile               # Container for cloud deployment
├── Procfile                 # Process definition
├── render.yaml              # One-click Render.com deployment
├── pyproject.toml           # Build configuration (hatchling)
├── CHANGELOG.md
├── CONTRIBUTING.md          # This file
├── LICENSE
├── README.md                # This file (English)
└── README.de.md             # German version
```

---

## Known Limitations

- **`env_hydro_history`**: The historical hourly data endpoint is currently returning 404 errors from hydrodaten.admin.ch (BUG-01 – under investigation). The tool will return download links as a fallback.
- **NABEL**: Near-real-time data only; no historical time series via this server.
- **Natural hazards**: Bulletin availability depends on SLF/BAFU publication schedule.
- **Wildfire danger**: Regional granularity varies by season and data availability.

---

## Testing

```bash
# Unit tests (no API keys or network required)
PYTHONPATH=src pytest tests/ -m "not live"

# Integration tests (requires live BAFU APIs)
PYTHONPATH=src pytest tests/ -m "live"

# Linting
ruff check src/
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License — see [LICENSE](LICENSE)

Source data is subject to BAFU terms of use. Attribution to BAFU is required when using their data.

---

## Author

malkreide · [github.com/malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **Data:** [BAFU / Bundesamt für Umwelt](https://www.bafu.admin.ch) · [hydrodaten.admin.ch](https://hydrodaten.admin.ch) · [naturgefahren.ch](https://naturgefahren.ch) · [opendata.swiss](https://opendata.swiss/en/organization/bafu)
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Related:**

| Server | Description |
|---|---|
| [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) | City of Zurich open data (OSTLUFT air quality, weather, parking, geodata) |
| [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) | Swiss public transport – OJP 2.0 journey planning, SIRI-SX disruptions |
| [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) | GBFS shared mobility, EV charging, DATEX II traffic |
| [swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp) | BFS STAT-TAB – 682 statistical datasets |

**Synergy example:** *"What was the air quality at Schulhaus Leutschenbach today – and how does it compare to the national NABEL average?"*  
→ `zurich-opendata-mcp` (OSTLUFT, local) + `swiss-environment-mcp` (NABEL, national)

- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
