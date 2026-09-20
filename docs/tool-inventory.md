# Tool-Inventar — swiss-environment-mcp (Phase-2-Bestandsaufnahme)

> **Historischer Schnappschuss, keine laufende Referenz.** Dieses Dokument hält
> den Planungsstand vom 19.07.2026 fest und wird bewusst nicht fortgeschrieben —
> die Update-Notizen unten tragen die Entwicklung nach. Wer den **heutigen**
> Stand braucht, liest ihn dort, wo er erzwungen wird:
>
> | Frage | Quelle der Wahrheit |
> |---|---|
> | Welche Tools gibt es? | `tool-snapshot.json` (CI-Gate `tool_snapshot.py check`) |
> | Welche Hosts dürfen kontaktiert werden? | `ALLOWED_HOSTS` in `src/swiss_environment_mcp/api_client.py` |
> | Welche Quelle bedient welches Tool? | Tool-Tabelle in `README.md` / `README.de.md` |
>
> **Stand 20.09.2026 (v0.7.0): 21 Tools in 7 Clustern, 3 Resources.** Die
> Zahlen im Abschnitt 1 unten sind die vom 19.07. und damit überholt.

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

**Egress-Allow-List (Stand 2026-07-26):** `www.hydrodaten.admin.ch`,
`opendata.swiss`, `www.waldbrandgefahr.ch`, `www.bafu.admin.ch`,
`map.bafu.admin.ch`, `lindas.admin.ch`, `measurement-api.slf.ch`, `aws.slf.ch`,
`www.jagdstatistik.ch`. (`www.naturgefahren.ch` entfernt — API stillgelegt, nur
noch Text-Link; `env_hazard_*` sind netzwerkfreie Routing-Tools.)

---

> **Update Phase 3:** Cluster **Wasser** nutzt neu LINDAS-SPARQL als Primärpfad
> (Inkrement 1). Neu: Cluster **Schnee/SLF** (`env_snow_stations`,
> `env_snow_current`, `env_avalanche_bulletin`, Inkrement 2) und Cluster **Jagd**
> (`env_hunting_species`, `env_hunting_stats`, Inkrement 3). Der
> SLF-IMIS-Niederschlagssensor wird bewusst nicht als Tool angebunden
> (Abgrenzung meteoswiss).
>
> **Update Hydro-Erweiterung Phase 2 (2026-07-25):** Neu `env_bathing_water`
> (Badegewässerqualität aus dem LINDAS-Cube `ubd01041prod`, Cluster Wasser) —
> Stand jetzt **18 Tools in 6 Clustern** (Budget 18 ausgeschöpft). Der gesamte
> LINDAS-Zugriff läuft über das extraktionsfähige Modul `lindas/`
> (`client.py` + `cube.py`, siehe Architektur-Notiz in beiden READMEs).
>
> **Update v0.5.0 (2026-07-28):** Neuer Cluster **Fluglärm**
> (`env_noise_aircraft_at`, `env_noise_aircraft_registers`,
> `env_noise_limits_check`) über den BAZL-Lärmbelastungskataster auf
> `api3.geo.admin.ch` — Stand **21 Tools in 7 Clustern**. Damit ist das
> Tool-Budget ausgeschöpft; weitere Quellen gehören in einen eigenen Server.
>
> **Update v0.6.0 (2026-08-03):** `www.hydrodaten.admin.ch` ist **aus der
> Egress-Allow-List entfernt** (SEC-021). Alle REST-Endpoints unter
> `/lhg/az/*` sind stillgelegt (404), die Hydrologie kommt vollständig über
> LINDAS; die Domain erscheint nur noch als Text-Link in der Tool-Ausgabe. Die
> Liste im Abschnitt oben führt sie noch — sie ist auf den 26.07. datiert.
> Massgeblich ist `ALLOWED_HOSTS` im Quelltext: `opendata.swiss`,
> `www.waldbrandgefahr.ch`, `www.bafu.admin.ch`, `map.bafu.admin.ch`,
> `lindas.admin.ch`, `measurement-api.slf.ch`, `aws.slf.ch`,
> `www.jagdstatistik.ch`, `api3.geo.admin.ch`.

## 2. Geplante Erweiterung (Phase-1-Probe abgeschlossen)

| Quelle | Cluster | Neue Hosts (künftig) | Probe-Doc |
|---|---|---|---|
| LINDAS-Hydro (SPARQL) ✅ umgesetzt | Wasser | `lindas.admin.ch` | `docs/probe-lindas-hydro.md` |
| SLF-Datenservice ✅ umgesetzt | Schnee/SLF | `measurement-api.slf.ch`, `aws.slf.ch` | `docs/probe-slf.md` |
| Jagdstatistik ✅ umgesetzt | Jagd | `www.jagdstatistik.ch` | `docs/probe-jagdstatistik.md` |
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
