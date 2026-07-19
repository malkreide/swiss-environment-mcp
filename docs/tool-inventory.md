# Tool-Inventar — swiss-environment-mcp (Phase-2-Bestandsaufnahme)

**Stand:** 2026-07-19
**Zweck:** Inventar der bestehenden Tools vor der geplanten Erweiterung um die drei
Phase-1-geprobten Quellen (LINDAS-Hydro, SLF, Jagdstatistik), inkl. Abgrenzung
gegen `meteoswiss-mcp` (Schnee-/Niederschlags-Überschneidung).

---

## 1. Bestehende Tools (12) in 4 Clustern

### Luft (3) — Quelle: BAFU NABEL / opendata.swiss
| Tool | Zweck | Netzwerk |
|---|---|---|
| `env_nabel_stations` | 16 NABEL-Messstationen auflisten | statisch |
| `env_nabel_current` | Metadaten + Datenlinks einer NABEL-Station | opendata.swiss |
| `env_air_limits_check` | Messwert gegen LRV/WHO-Grenzwerte prüfen | rein lokal |

### Wasser / Hydrologie (4) — Quelle: hydrodaten.admin.ch / opendata.swiss
| Tool | Zweck | Netzwerk |
|---|---|---|
| `env_hydro_stations` | Hydro-Messstationen auflisten (Filter Kanton/Gewässer) | hydrodaten.admin.ch |
| `env_hydro_current` | Aktueller Pegel/Abfluss/Temperatur einer Station | hydrodaten.admin.ch |
| `env_hydro_history` | Historische Werte (⚠️ BUG-01: Endpoint 404, Fallback-Links) | hydrodaten.admin.ch |
| `env_flood_warnings` | Aktuelle Hochwasserwarnungen (5 Stufen) | hydrodaten.admin.ch |

### Naturgefahren (3) — Quelle: naturgefahren.ch / waldbrandgefahr.ch (SLF/BAFU)
| Tool | Zweck | Netzwerk |
|---|---|---|
| `env_hazard_overview` | Naturgefahren-Bulletin Schweiz | naturgefahren.ch |
| `env_hazard_regions` | Regionsspezifische Gefahrenwarnungen | naturgefahren.ch |
| `env_wildfire_danger` | Waldbrandgefahren-Index (5 Stufen) | waldbrandgefahr.ch |

### Umweltdaten / Katalog (2) — Quelle: opendata.swiss (CKAN)
| Tool | Zweck | Netzwerk |
|---|---|---|
| `env_bafu_datasets` | BAFU-Datensätze auf opendata.swiss suchen | opendata.swiss |
| `env_bafu_dataset_detail` | Metadaten + Download-URLs eines Datensatzes | opendata.swiss |

### MCP-Resources (3, read-only)
- `env://grenzwerte/luft` — LRV + WHO-2021-Grenzwerte
- `env://nabel/stationen` — vollständige NABEL-Stationsliste
- `env://hochwasser/gefahrenstufen` — Hochwasser-Gefahrenstufen 1–5

**Egress-Allow-List (aktuell):** `www.hydrodaten.admin.ch`, `opendata.swiss`,
`www.naturgefahren.ch`, `www.waldbrandgefahr.ch`, `www.bafu.admin.ch`,
`map.bafu.admin.ch`.

---

> **Update Phase 3:** Cluster **Wasser** nutzt neu LINDAS-SPARQL als Primärpfad
> (Inkrement 1, gemergt). Neu hinzugekommen ist der Cluster **Schnee/SLF** mit
> `env_snow_stations`, `env_snow_current`, `env_avalanche_bulletin` (Inkrement 2)
> — Stand jetzt **15 Tools**. Der SLF-IMIS-Niederschlagssensor wird bewusst nicht
> als Tool angebunden (Abgrenzung meteoswiss).

## 2. Geplante Erweiterung (Phase-1-Probe abgeschlossen)

| Quelle | Cluster | Neue Hosts (künftig) | Probe-Doc |
|---|---|---|---|
| LINDAS-Hydro (SPARQL) ✅ umgesetzt | Wasser | `lindas.admin.ch` | `docs/probe-lindas-hydro.md` |
| SLF-Datenservice ✅ umgesetzt | Schnee/SLF | `measurement-api.slf.ch`, `aws.slf.ch` | `docs/probe-slf.md` |
| Jagdstatistik | (neu) Wildtiere | `www.jagdstatistik.ch` | `docs/probe-jagdstatistik.md` |

---

## 3. Überschneidungsanalyse mit `meteoswiss-mcp`

`meteoswiss-mcp` bietet 6 Tools: `meteo_current`, `meteo_forecast`,
`meteo_stations`, `meteo_warnings`, `meteo_climate_normals`, `meteo_school_check`.

| Berührungspunkt | meteoswiss-mcp | swiss-environment-mcp | Duplikat? |
|---|---|---|---|
| **Niederschlagsmenge (mm)** | ✅ Messnetz + Prognose + Klimanormwerte | (SLF-IMIS-Sensor nur als Schnee-Kontext geplant) | **zu vermeiden** |
| **Schneefall (Wetterlage)** | ✅ Wettercode (`meteo_current/forecast`) | ❌ | nein |
| **Schneehöhe / Neuschnee (Boden)** | ❌ | ✅ SLF (geplant) | nein |
| **Lawinenwarnstufe** | ❌ | ✅ SLF-Bulletin (geplant) + `env_hazard_*` | nein |
| **Warnungen** | Wetter (Sturm/Gewitter/Hitze) | Naturgefahren (Hochwasser/Lawine/Waldbrand) | komplementär |

**Fazit:** Die einzige echte Duplikationsgefahr betrifft **Niederschlag**. Der
SLF-IMIS-Niederschlagssensor wird deshalb nur als Begleitkontext zur Schneedecke
geführt und **nie als eigenständiges Niederschlags-Tool** exponiert. Die
verbindliche Aufteilung ist als **Zuständigkeitsmatrix** in den «Known
Limitations» beider READMEs (`swiss-environment-mcp` und `meteoswiss-mcp`)
dokumentiert.
