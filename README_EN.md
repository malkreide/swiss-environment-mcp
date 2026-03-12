# 🌿 Swiss Environment MCP

🇬🇧 English | [🇩🇪 Deutsch](README.md)

**MCP Server for Swiss Environmental Data from BAFU (Federal Office for the Environment)** – Air quality, hydrology, natural hazards and environmental indicators.

Enables AI assistants like Claude, ChatGPT and other MCP-compatible systems to access real-time environmental data from Swiss federal authorities.

---

## 🧰 Tools (12)

### 🌬️ Air Quality / NABEL (3 Tools)
| Tool | Description |
|------|-------------|
| `env_nabel_stations` | List all 16 NABEL air quality monitoring stations |
| `env_nabel_current` | Current air quality data (NO₂, O₃, PM10, PM2.5, SO₂, CO) |
| `env_air_limits_check` | Compare measurements against Swiss LRV limits and WHO 2021 guidelines |

### 💧 Water / Hydrology (4 Tools)
| Tool | Description |
|------|-------------|
| `env_hydro_stations` | Filter hydrological measuring stations by canton or water body |
| `env_hydro_current` | Current water level, flow rate and temperature at a station |
| `env_hydro_history` | Historical hourly values (up to 30 days) with download links |
| `env_flood_warnings` | Active flood warnings filtered by danger level and canton |

### 🏔️ Natural Hazards (3 Tools)
| Tool | Description |
|------|-------------|
| `env_hazard_overview` | Current natural hazard bulletin (SLF/BAFU) in DE/FR/IT/EN |
| `env_hazard_regions` | Region-specific warnings (floods, avalanches, rockfall) |
| `env_wildfire_danger` | Wildfire danger index by canton and region |

### 📊 Environmental Data Catalog (2 Tools)
| Tool | Description |
|------|-------------|
| `env_bafu_datasets` | Search BAFU datasets on opendata.swiss (CKAN API) |
| `env_bafu_dataset_detail` | Full metadata and download URLs for a dataset |

---

## ⚡ Quick Start

```bash
# Recommended: uvx (no installation needed)
uvx swiss-environment-mcp

# Or via pip
pip install swiss-environment-mcp
python -m swiss_environment_mcp.server
```

### Claude Desktop Configuration

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

---

## 💬 Example Queries

- "What is the current air quality at the NABEL station Zürich-Kaserne?"
- "Does a NO₂ reading of 45 µg/m³ exceed the Swiss limit?"
- "Which flood warnings are currently active in Switzerland?"
- "What is the current water level of the Limmat in Zurich?"
- "What is the wildfire danger in Canton Valais right now?"
- "Show all BAFU biodiversity datasets on opendata.swiss"

---

## 🔗 Data Sources

| Source | Data | License |
|--------|------|---------|
| [hydrodaten.admin.ch](https://www.hydrodaten.admin.ch) | Water levels, flow rates, temperatures (10-min intervals) | BAFU OGD |
| [naturgefahren.ch](https://www.naturgefahren.ch) | Natural hazard bulletin (SLF/BAFU) | BAFU/SLF |
| [waldbrandgefahr.ch](https://www.waldbrandgefahr.ch) | Wildfire danger index | BAFU |
| [opendata.swiss](https://opendata.swiss/en/organization/bafu) | BAFU data catalog (CKAN API) | OGD |

All data: publicly accessible, no authentication required.

---

## 📄 License

[MIT](LICENSE) – Source data subject to BAFU terms of use.  
**Attribution required:** BAFU must be cited as the source when using their data.
