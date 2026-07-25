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

<p align="center">
  <img src="assets/demo.svg" alt="Demo: Claude queries NABEL air quality via a swiss-environment-mcp tool call and gets a WHO 2021 compliance check" width="820">
</p>

---

## Overview

**swiss-environment-mcp** gives AI assistants like Claude direct access to real-time environmental data from Swiss federal authorities – no API keys required. Air quality readings from the national NABEL monitoring network, hydrological gauging stations, natural hazard bulletins, and the full BAFU dataset catalogue are all accessible through a single standardised MCP interface.

The server covers four thematic clusters: air quality (NABEL), hydrology, natural hazards, and the BAFU open data catalogue. Each cluster maps to a group of purpose-built tools that translate raw agency data into clean JSON responses.

**Anchor demo query:** *"What is the current air quality at the NABEL station Zürich-Kaserne – and does it comply with WHO 2021 guidelines?"*
→ [More use cases by audience](./EXAMPLES.md) →

---

## Features

- 🌬️ **Air quality monitoring** – 16 NABEL stations, NO₂/O₃/PM10/PM2.5/SO₂/CO, Swiss LRV + WHO 2021 limit checks
- 💧 **Hydrology** – water levels, flow rates, temperatures across Swiss gauging stations
- 🚨 **Flood warnings** – active alerts filtered by danger level and canton
- 🏔️ **Natural hazard bulletin** – SLF/BAFU bulletin in DE/FR/IT/EN, region-specific warnings
- 🔥 **Wildfire danger** – canton- and region-level fire danger index
- ❄️ **Snow & avalanches (SLF)** – snow depth, new snow per IMIS station; avalanche danger levels (EAWS)
- 🦌 **Hunting statistics** – cull & game-loss figures per species, canton and year (federal hunting statistics)
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

All tools share the stable `env_` name prefix — a deliberate namespace choice so
that the server's tools are recognisable and unlikely to collide when several MCP
servers are mounted together. Tool definitions (name, description, input schema)
are pinned via `tool-snapshot.json`; changes require a CHANGELOG entry (see
CONTRIBUTING).

**Tool budget (18 tools, 6 clusters).** Every tool maps to a distinct user
question, not to a REST endpoint — there is no CRUD/endpoint mirroring, and the
anchor queries are each answerable in a single call. The count sits above the
≤12 rule of thumb because the server deliberately spans six environmental
domains (air, water, hazards, snow, hunting, catalogue), each needing a
list/detail pair or a domain-specific action. Further consolidation was
considered and rejected: the `*_stations`/`*_current` pairs (NABEL, hydro, snow)
serve genuinely different intents (discovery vs. reading a known station) and
collapsing them would overload a single tool's parameters. Adding a seventh
domain would trigger a review of whether some listings should migrate to MCP
resources instead of tools.

### 🌬️ Air Quality / NABEL (3 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_nabel_stations` | List all 16 NABEL monitoring stations with location type and canton | NABEL / BAFU |
| `env_nabel_current` | Current air quality data for a station (NO₂, O₃, PM10, PM2.5, SO₂, CO) | NABEL / BAFU |
| `env_air_limits_check` | Compare a measurement against Swiss LRV limits and WHO 2021 guidelines | Built-in |

### 💧 Hydrology (5 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_hydro_stations` | Filter hydrological gauging stations by canton or water body | **LINDAS SPARQL** → hydrodaten.admin.ch (fallback) |
| `env_hydro_current` | Current water level, flow rate and temperature at a station | **LINDAS SPARQL** → hydrodaten.admin.ch (fallback) |
| `env_hydro_history` | Historical hourly values (up to 30 days) with download links ⚠️ | hydrodaten.admin.ch |
| `env_flood_warnings` | Active flood warnings filtered by danger level and canton | hydrodaten.admin.ch |
| `env_bathing_water` | Bathing water quality (E.coli, enterococci) per bathing site — multi-year time series | **LINDAS SPARQL** (data cube `ubd0104`) |

### 🏔️ Natural Hazards (3 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_hazard_overview` | Current natural hazard bulletin (SLF/BAFU) in DE/FR/IT/EN | naturgefahren.ch |
| `env_hazard_regions` | Region-specific warnings (floods, avalanches, rockfall) | naturgefahren.ch |
| `env_wildfire_danger` | Wildfire danger index by canton and region | waldbrandgefahr.ch |

### ❄️ Snow & Avalanches / SLF (3 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_snow_stations` | List automatic SLF/IMIS snow measurement stations (by canton) | measurement-api.slf.ch |
| `env_snow_current` | Current snow depth (HS) and 24 h new snow (HN_1D) per station, in cm | measurement-api.slf.ch |
| `env_avalanche_bulletin` | Avalanche danger levels (EAWS 1–5) per warning region, seasonal | aws.slf.ch |

### 🦌 Hunting & Wildlife (2 tools)

| Tool | Description | Data Source |
|---|---|---|
| `env_hunting_species` | List the 36 species tracked by the federal hunting statistics (with codes) | jagdstatistik.ch (embedded) |
| `env_hunting_stats` | Cull / game-loss / population figures per species, canton and year (2015–2024) | jagdstatistik.ch |

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
| *"Is the water quality at Strandbad Küsnacht safe for swimming?"* | `env_bathing_water` |
| *"Active flood warnings in Switzerland?"* | `env_flood_warnings` |
| *"Natural hazard bulletin for Graubünden?"* | `env_hazard_overview` |
| *"Wildfire danger in Canton Valais?"* | `env_wildfire_danger` |
| *"BAFU biodiversity datasets on opendata.swiss?"* | `env_bafu_datasets` |

---

## 🛡️ Safety & Limits

| Aspect | Details |
|--------|---------|
| **Access** | Read-only (`readOnlyHint: true`) — the server cannot modify or delete any data |
| **Personal data** | No personal data — all sources are aggregated, public environmental measurements |
| **Rate limits** | Built-in per-query caps (e.g. max 30 days hydrology history, 50 dataset search results) |
| **Timeout** | 30 seconds per API call |
| **Authentication** | No API keys required — all BAFU endpoints are publicly accessible |
| **Licenses** | BAFU Open Government Data (OGD) — free reuse with mandatory attribution |
| **Terms of Service** | Subject to ToS of the respective data sources: [BAFU / opendata.swiss](https://opendata.swiss/en/organization/bafu), [hydrodaten.admin.ch](https://hydrodaten.admin.ch), [naturgefahren.ch](https://naturgefahren.ch), [waldbrandgefahr.ch](https://waldbrandgefahr.ch) |

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

### Architecture note — extractable `lindas/` module

All LINDAS SPARQL access goes through the deliberately **extractable**
`src/swiss_environment_mcp/lindas/` module, built as three strict layers:
`client.py` knows only SPARQL and HTTP (GET/POST, 45 s client-side timeout,
`QueryError` carrying the server's MALFORMED message, 2 s/4 s/8 s retry);
`cube.py` knows the cube.link vocabulary (mandatory `observationSet`
two-phase access, version deduplication via `schema:expires`, code→label
resolution, licence lookup); the tools only ever call `cube.py`. The module
will be lifted into a shared `lindas-mcp` as soon as a second server uses
LINDAS (candidate: `wsl-envidat-mcp`).

### Data Sources

| Source | Data | Licence |
|---|---|---|
| [lindas.admin.ch](https://lindas.admin.ch) | Current hydrology (level, discharge, water temperature) and bathing water quality via SPARQL | BAFU Open-Use / OGD (declared per graph/dataset — each response carries a licence field) |
| [hydrodaten.admin.ch](https://hydrodaten.admin.ch) | Water levels, flow rates, temperatures (REST fallback) | BAFU OGD |
| [naturgefahren.ch](https://naturgefahren.ch) | Natural hazard bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://waldbrandgefahr.ch) | Wildfire danger index | BAFU |
| [SLF data service](https://www.slf.ch/en/services-and-products/slf-data-service/) | Snow depth, new snow (IMIS); avalanche bulletin | SLF (WSL) CC BY 4.0 |
| [jagdstatistik.ch](https://www.jagdstatistik.ch/de/home) | Federal hunting statistics (cull, game loss, population) | BAFU — source attribution required (no explicit licence published) |
| [opendata.swiss](https://opendata.swiss/en/organization/bafu) | BAFU data catalogue (CKAN API) | OGD |

All data: publicly accessible, no authentication required.  
**Attribution required:** BAFU / SLF (WSL) must be cited as the source when using their data.

---

## Project Structure

```
swiss-environment-mcp/
├── src/swiss_environment_mcp/
│   ├── __init__.py          # Package
│   ├── server.py            # FastMCP server: 12 tools, 3 resources
│   ├── api_client.py        # HTTP client + egress allow-list (SSRF guard)
│   └── logging_setup.py     # structlog -> stderr
├── tests/
│   ├── test_unit.py         # Mocked unit tests (no network) — CI default
│   ├── test_integration.py  # Live API tests (marker: live)
│   └── test_20_scenarios.py # Live scenario coverage
├── scripts/tool_snapshot.py # Tool-definition hash snapshot (rug-pull guard)
├── docs/                    # security.md, scaling.md, roadmap.md
├── .github/
│   ├── dependabot.yml       # Monthly dependency/action updates
│   └── workflows/           # ci.yml, security.yml (gitleaks), live-tests.yml, publish.yml
├── Dockerfile               # Multi-stage, non-root container
├── render.yaml / Procfile   # Cloud deployment
├── tool-snapshot.json       # Committed tool-definition snapshot
├── .env.example             # Non-secret config template
└── pyproject.toml           # Build configuration (hatchling)
```

> **Single-module layout (rationale, audit ARCH-011):** the 12 tools live in one
> `server.py` rather than a `tools/` package. They are thin, uniform wrappers over
> `api_client.py` sharing the same input/response patterns, so a single
> well-sectioned module stays more navigable than 4 near-identical files. This is a
> deliberate, documented deviation; a split is revisited if tool logic grows non-uniform.

---

## MCP Protocol Version & Maintenance

- **MCP protocol:** negotiated at `initialize` time and handled by the pinned MCP
  SDK (`mcp[cli]`). The SDK version is the canonical pin; SDK/protocol updates land
  via Dependabot PRs (`.github/dependabot.yml`, monthly).
- **Tool-definition stability (audit SEC-022):** any change to a tool's name,
  description or parameters changes `tool-snapshot.json`; CI fails until the snapshot
  is regenerated and a `CHANGELOG` entry + version bump are added.
- **Update policy:** review Dependabot PRs monthly; bump the version (semver) on any
  tool-definition or behaviour change.

## Lifecycle Phase

This server is in **Phase 1 (read-only)** — all tools read-only, no auth, no side
effects. The phase model and prerequisites for Phase 2 (write/auth) are in
[`docs/roadmap.md`](docs/roadmap.md). Security architecture (SSRF/egress, secret
management, lethal-trifecta assessment): [`docs/security.md`](docs/security.md).
Scaling/session strategy: [`docs/scaling.md`](docs/scaling.md).

---

## Known Limitations

- **Hydrology via LINDAS**: `env_hydro_current`, `env_hydro_stations` and `env_flood_warnings` query the BAFU LINDAS SPARQL endpoint (typed live values: level, discharge, water temperature, danger level). LINDAS holds **current values only** (one observation per station) — it is **not** a historical time series. See [`docs/probe-lindas-hydro.md`](docs/probe-lindas-hydro.md).
- **Historical hydrology / `env_hydro_history` (BUG-01 resolved)**: the old `hydrodaten.admin.ch/lhg/az/*` REST endpoints (hourly CSV, `warnings.json`, station JSON) are **decommissioned (404)**. `env_flood_warnings` now uses LINDAS `dangerLevel` instead. Real historical time series (daily / long-term means — e.g. *summer 2024 vs. long-term average*) are **not freely available via API**; they must be ordered from the **BAFU Hydrological Enquiry Service** (abfragezentrale@bafu.admin.ch). `env_hydro_history` returns the latest LINDAS value plus this access path.
- **Flood warnings**: `env_flood_warnings` reads LINDAS `dangerLevel`; a canton filter is not available there (LINDAS carries no canton code), so it is reported but not applied.
- **Bathing water quality (`env_bathing_water`)**: reads the LINDAS data cube `foen/ubd01041prod` — the only hydro cube with a real multi-year time series (seasonal samples since 2020). Data is refreshed **annually after the bathing season** (no real-time monitoring), and the survey covers only the officially reported bathing sites (many popular lidos are not part of it). The licence is declared at graph/dataset level, not on the cube; every response therefore carries an explicit licence field — with an honest «not declared» note where none exists. See [`docs/probe-lindas-hydro.md`](docs/probe-lindas-hydro.md) (addendum N1–N7).
- **No groundwater data in LINDAS**: verified 2026-07-24 via multilingual cube search — LINDAS contains **no groundwater cube** (NAQUA groundwater levels are not available via SPARQL).
- **NABEL**: Near-real-time data only; no historical time series via this server.
- **Natural hazards**: Bulletin availability depends on SLF/BAFU publication schedule.
- **Wildfire danger**: Regional granularity varies by season and data availability.
- **Hunting statistics (`env_hunting_stats`)**: The `jagdstatistik.ch` backend is **undocumented** (a content-negotiated web-app endpoint). A schema-guard degrades gracefully if the structure changes. Species/canton/datatype lookups are embedded (harvested 2026-07-19); figures are fetched live for 2015–2024. **Licence (researched 2026-07-19):** the data is owned by **BAFU** (compiled from cantonal offices; site tech by Wildtier Schweiz) and is **not** published as a licensed dataset on opendata.swiss; **no explicit licence is stated on the source**. Responses therefore require source attribution to BAFU; formal licence confirmation from BAFU is still pending. See [`docs/probe-jagdstatistik.md`](docs/probe-jagdstatistik.md).

### Responsibility matrix — water, snow & precipitation (delineation vs. `meteoswiss-mcp`)

To avoid duplicating **water, snow and precipitation** data across the portfolio,
responsibilities are split as follows. `meteoswiss-mcp` owns atmospheric
precipitation and weather; `swiss-environment-mcp` owns surface waters
(BAFU domain: discharge, water level, water temperature, bathing quality),
snow on the ground and avalanche danger. Checked against the actual LINDAS
cube dimensions (2026-07-24): there is **no overlap in measured quantities**.

| Data | swiss-environment-mcp (BAFU / SLF) | meteoswiss-mcp (MeteoSwiss) |
|---|---|---|
| Discharge (m³/s) | ✅ `env_hydro_current` (LINDAS `hydro/river`) | ❌ |
| Water level (m a.s.l.) | ✅ `env_hydro_current` (LINDAS `hydro/river` + `lake`) | ❌ |
| Water temperature (°C) | ✅ `env_hydro_current` | ❌ (measures air temperature) |
| Bathing water quality (E.coli etc.) | ✅ `env_bathing_water` (LINDAS `ubd0104`) | ❌ |
| Snow depth on the ground (`HS`) | ✅ `env_snow_current` (SLF IMIS) | ❌ |
| Fresh snow 24 h (`HN_1D`) | ✅ `env_snow_current` (SLF IMIS) | ❌ |
| Avalanche danger level | ✅ `env_avalanche_bulletin` (SLF, EAWS 1–5) | ❌ |
| Snowfall as a current weather condition | ❌ | ✅ `meteo_current` / `meteo_forecast` (weather code) |
| Precipitation amount (mm): measurement network, forecast, climate normals | ❌ | ✅ `meteo_current` / `meteo_forecast` / `meteo_climate_normals` |
| Precipitation at SLF IMIS mountain stations | ✅ only as snow-cover context, **no standalone precipitation tool** | (MeteoSwiss network) |
| Weather warnings (storm, thunderstorm, heat) | ❌ | ✅ `meteo_warnings` |
| Natural-hazard warnings (flood, avalanche, wildfire) | ✅ `env_flood_warnings`, `env_hazard_*`, `env_wildfire_danger` | ❌ |

**Rule:** everything **in and on water bodies** (discharge, level, water
temperature, bathing quality), snow **on the ground** and **avalanche** danger
belong to `swiss-environment-mcp` (BAFU/SLF); **atmospheric precipitation**
(rain/snowfall as mm) plus weather, forecast, warnings and climate normals belong
to `meteoswiss-mcp`. The SLF IMIS precipitation endpoint (`RR_10MIN_SUM`) is
deliberately **not** wired up as a tool, so it does not duplicate MeteoSwiss. The
snow/avalanche tools are live (see [`docs/probe-slf.md`](docs/probe-slf.md)).
*TODO (out of scope here): mirror this matrix in the `meteoswiss-mcp` README —
that repository is not part of this change.*

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

See [CONTRIBUTING.md](CONTRIBUTING.md) (English) · [CONTRIBUTING.de.md](CONTRIBUTING.de.md) (German)

---

## Security

Security policy and posture: [SECURITY.md](SECURITY.md) (English) · [SECURITY.de.md](SECURITY.de.md) (German).
Full security architecture: [`docs/security.md`](docs/security.md).

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License — see [LICENSE](LICENSE)

Source data is subject to BAFU terms of use. Attribution to BAFU is required when using their data.

---

## Author

Hayal Oezkan · [github.com/malkreide](https://github.com/malkreide)

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

<!-- mcp-name: io.github.malkreide/swiss-environment-mcp -->

<!-- BEGIN GENERATED: install -->
## Installation

Run via [`uv`](https://docs.astral.sh/uv/)'s `uvx` — no clone or manual install needed. Add to your MCP client config (`mcpServers` for Claude Desktop, Cursor and Windsurf; use a top-level `servers` key for VS Code in `.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "swiss-environment-mcp": {
      "command": "uvx",
      "args": [
        "swiss-environment-mcp"
      ]
    }
  }
}
```
<!-- END GENERATED: install -->
