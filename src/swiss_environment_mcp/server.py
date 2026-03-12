"""
Swiss Environment MCP Server

MCP-Server für Schweizer Umweltdaten des BAFU (Bundesamt für Umwelt).
Bietet 12 Tools in 4 thematischen Clustern:

  Luft (3):        env_nabel_stations, env_nabel_current, env_air_limits_check
  Wasser (4):      env_hydro_stations, env_hydro_current, env_hydro_history, env_flood_warnings
  Naturgefahren (3): env_hazard_overview, env_hazard_regions, env_wildfire_danger
  Umweltdaten (2): env_bafu_datasets, env_bafu_dataset_detail

Datenquellen:
  - BAFU NABEL (Nationale Luftmessstation-Daten)
  - hydrodaten.admin.ch (Hydrologische Messdaten, 10-Minuten-Intervall)
  - naturgefahren.ch (Naturgefahren-Bulletin SLF/BAFU)
  - waldbrandgefahr.ch (Waldbrandgefahren-Index)
  - opendata.swiss CKAN (BAFU-Datenkatalog)

Alle Daten: öffentlich, keine Authentifizierung erforderlich.
Lizenz der Quelldaten: BAFU-Nutzungsbedingungen / Open Government Data (OGD)
"""

import json
import os
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import api_client as api

# --- Konstanten ---------------------------------------------------------------

# Grenzwerte gemäss Luftreinhalte-Verordnung (LRV) Schweiz, µg/m³
SWISS_LRV_LIMITS: dict[str, float] = {
    "NO2":  30.0,   # Jahresmittelwert
    "PM10": 20.0,   # Jahresmittelwert (WHO 2021: 15)
    "PM2.5": 10.0,  # Jahresmittelwert (WHO 2021: 5)
    "O3":   100.0,  # Stundenmittelwert 98-Perzentil
    "SO2":  30.0,   # Jahresmittelwert
    "CO":   8000.0, # Tagesmittelwert
}

# WHO 2021 Richtwerte, µg/m³
WHO_2021_LIMITS: dict[str, float] = {
    "NO2":  10.0,
    "PM10": 15.0,
    "PM2.5": 5.0,
    "O3":   60.0,   # Jahresmittelwert peak season
    "SO2":  40.0,   # 24-Stunden-Mittelwert
}

# NABEL-Stationen mit Standorttyp
NABEL_STATIONS: dict[str, dict[str, str]] = {
    "BAS": {"name": "Basel", "canton": "BS", "type": "Stadtgebiet"},
    "BER": {"name": "Bern-Bollwerk", "canton": "BE", "type": "Stadtgebiet"},
    "DAV": {"name": "Davos", "canton": "GR", "type": "Ländlich/Bergstation"},
    "DUB": {"name": "Dübendorf", "canton": "ZH", "type": "Vorort"},
    "HAE": {"name": "Härkingen", "canton": "SO", "type": "Ländlich/Regional"},
    "JUN": {"name": "Jungfraujoch", "canton": "BE", "type": "Bergstation/Hintergrund"},
    "LAE": {"name": "Lägern", "canton": "ZH", "type": "Ländlich/Hintergrund"},
    "LAU": {"name": "Lausanne", "canton": "VD", "type": "Stadtgebiet"},
    "LUG": {"name": "Lugano", "canton": "TI", "type": "Stadtgebiet"},
    "MAG": {"name": "Magadino", "canton": "TI", "type": "Ländlich"},
    "PAY": {"name": "Payerne", "canton": "VD", "type": "Ländlich/Regional"},
    "RIG": {"name": "Rigi-Seebodenalp", "canton": "SZ", "type": "Bergstation"},
    "SIO": {"name": "Sitten/Sion", "canton": "VS", "type": "Stadtgebiet"},
    "TAE": {"name": "Tänikon", "canton": "TG", "type": "Ländlich/Agrar"},
    "ZUE": {"name": "Zürich-Kaserne", "canton": "ZH", "type": "Stadtgebiet/Verkehr"},
    "ZUR": {"name": "Zürich-Rosengartenstrasse", "canton": "ZH", "type": "Verkehr"},
}

# Hochwasser-Gefahrenstufen
FLOOD_DANGER_LEVELS: dict[int, dict[str, str]] = {
    1: {"label": "Keine Gefahr", "color": "grün",   "description": "Normaler Wasserstand"},
    2: {"label": "Mässige Gefahr", "color": "gelb",  "description": "Erhöhter Wasserstand, lokale Überschwemmungen möglich"},
    3: {"label": "Erhebliche Gefahr", "color": "orange", "description": "Bedeutende Überschwemmungen"},
    4: {"label": "Grosse Gefahr", "color": "rot",    "description": "Grosse Überschwemmungen"},
    5: {"label": "Sehr grosse Gefahr", "color": "lila", "description": "Katastrophale Überschwemmungen"},
}

# Waldbrand-Gefahrenstufen
WILDFIRE_DANGER_LEVELS: dict[int, dict[str, str]] = {
    1: {"label": "Gering",       "color": "grün"},
    2: {"label": "Mässig",       "color": "gelb"},
    3: {"label": "Erheblich",    "color": "orange"},
    4: {"label": "Gross",        "color": "rot"},
    5: {"label": "Sehr gross",   "color": "dunkelrot"},
}


# --- Server-Initialisierung ---------------------------------------------------

mcp = FastMCP(
    "swiss_environment_mcp",
    instructions="""
    MCP-Server für Schweizer Umweltdaten des BAFU.
    Bietet Zugriff auf Luftqualität (NABEL), Hydrologiedaten (Flüsse/Seen),
    Hochwasserwarnungen, Naturgefahren-Bulletin und Waldbrandgefahr.
    Alle Daten stammen von Schweizer Bundesbehörden und sind öffentlich zugänglich.
    Zeitzone: Schweiz (CET/CEST). Masseinheiten: µg/m³ (Luft), m (Pegel), m³/s (Abfluss).
    """,
)


# --- Pydantic-Eingabemodelle --------------------------------------------------

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class NabelStationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' (lesbar) oder 'json' (strukturiert)",
    )


class NabelCurrentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    station: str = Field(
        ...,
        description="NABEL-Stationskürzel (z.B. 'ZUE' für Zürich-Kaserne, 'DUB' für Dübendorf)",
        min_length=2,
        max_length=10,
    )

    @field_validator("station")
    @classmethod
    def validate_station(cls, v: str) -> str:
        return v.upper().strip()


class AirLimitsCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pollutant: str = Field(
        ...,
        description="Schadstoff: 'NO2', 'PM10', 'PM2.5', 'O3', 'SO2', 'CO'",
    )
    value: float = Field(
        ...,
        description="Gemessener Wert in µg/m³ (bzw. µg/m³ für CO: mg/m³)",
        ge=0.0,
        le=100000.0,
    )
    averaging_period: str = Field(
        default="annual",
        description="Mittelungszeitraum: 'annual' (Jahresmittel), 'daily', 'hourly'",
    )

    @field_validator("pollutant")
    @classmethod
    def validate_pollutant(cls, v: str) -> str:
        return v.upper().strip()


class HydroStationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'ZH', 'BE', 'GR') – leer = alle Kantone",
        max_length=2,
    )
    water_body: str = Field(
        default="",
        description="Gewässername zum Filtern (z.B. 'Limmat', 'Rhein', 'Sihl')",
        max_length=60,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class HydroCurrentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    station_id: str = Field(
        ...,
        description="BAFU-Stationsnummer (z.B. '2099' für Zürich/Limmat-Unterwerk, '2243' für Sihl/Zürich)",
        min_length=2,
        max_length=10,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class HydroHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str = Field(
        ...,
        description="BAFU-Stationsnummer",
        min_length=2,
        max_length=10,
    )
    parameter: str = Field(
        default="Abfluss",
        description="Messparameter: 'Abfluss' (m³/s), 'Pegel' (m ü.M.), 'Temperatur' (°C)",
    )
    days: int = Field(
        default=7,
        description="Anzahl Tage in der Vergangenheit (1–30)",
        ge=1,
        le=30,
    )


class FloodWarningsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    min_level: int = Field(
        default=2,
        description="Minimale Gefahrenstufe (1–5): 1=keine, 2=mässig, 3=erheblich, 4=gross, 5=sehr gross",
        ge=1,
        le=5,
    )
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'ZH') – leer = ganze Schweiz",
        max_length=2,
    )


class HazardOverviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(
        default="de",
        description="Sprache: 'de', 'fr', 'it', 'en'",
    )


class HazardRegionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    region: str = Field(
        default="",
        description="Regionsname oder -code zum Filtern (z.B. 'Zürich', 'Graubünden')",
        max_length=60,
    )
    hazard_type: str = Field(
        default="",
        description="Gefahrentyp: 'hochwasser', 'lawinen', 'steinschlag', 'rutschungen' – leer = alle",
        max_length=30,
    )
    language: str = Field(default="de")


class WildfireDangerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(
        default="de",
        description="Sprache: 'de', 'fr', 'it'",
    )
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'ZH', 'VS', 'TI')",
        max_length=2,
    )


class BafuDatasetsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(
        default="",
        description="Suchbegriff (z.B. 'Luftqualität', 'Hochwasser', 'Biodiversität')",
        max_length=200,
    )
    rows: int = Field(
        default=10,
        description="Anzahl Resultate (1–50)",
        ge=1,
        le=50,
    )
    offset: int = Field(
        default=0,
        description="Offset für Paginierung",
        ge=0,
    )


class BafuDatasetDetailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    dataset_id: str = Field(
        ...,
        description="Dataset-ID oder Slug von opendata.swiss (z.B. 'nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen')",
        min_length=3,
        max_length=200,
    )


# --- Hilfsfunktionen ----------------------------------------------------------

def _format_flood_level(level: int) -> str:
    info = FLOOD_DANGER_LEVELS.get(level, {"label": "Unbekannt", "color": "grau", "description": ""})
    return f"Stufe {level} ({info['label']}, {info['color']})"


def _assess_air_quality(pollutant: str, value: float) -> dict[str, Any]:
    """Bewertet einen Messwert gegen Schweizer LRV und WHO-Grenzwerte."""
    lrv_limit = SWISS_LRV_LIMITS.get(pollutant)
    who_limit = WHO_2021_LIMITS.get(pollutant)
    result: dict[str, Any] = {
        "pollutant": pollutant,
        "value_µg_m3": value,
        "swiss_lrv": {
            "limit": lrv_limit,
            "exceeded": (value > lrv_limit) if lrv_limit else None,
            "ratio": round(value / lrv_limit, 2) if lrv_limit else None,
        },
        "who_2021": {
            "limit": who_limit,
            "exceeded": (value > who_limit) if who_limit else None,
            "ratio": round(value / who_limit, 2) if who_limit else None,
        },
    }
    return result


def _format_assessment_markdown(assessment: dict[str, Any]) -> str:
    """Formatiert eine Luftqualitätsbewertung als Markdown."""
    p = assessment["pollutant"]
    v = assessment["value_µg_m3"]
    lrv = assessment["swiss_lrv"]
    who = assessment["who_2021"]

    lines = [f"### Bewertung: {p} = **{v} µg/m³**\n"]

    if lrv["limit"]:
        status = "⚠️ **ÜBERSCHRITTEN**" if lrv["exceeded"] else "✅ Eingehalten"
        lines.append(f"**Schweizer LRV-Grenzwert:** {lrv['limit']} µg/m³ → {status} ({lrv['ratio']}×)")

    if who["limit"]:
        status = "⚠️ **ÜBERSCHRITTEN**" if who["exceeded"] else "✅ Eingehalten"
        lines.append(f"**WHO-Richtwert 2021:** {who['limit']} µg/m³ → {status} ({who['ratio']}×)")

    return "\n".join(lines)


# --- TOOLS: LUFT / NABEL ------------------------------------------------------

@mcp.tool(
    name="env_nabel_stations",
    annotations={
        "title": "NABEL-Messstationen auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def env_nabel_stations(params: NabelStationsInput) -> str:
    """
    Listet alle 16 NABEL-Messstationen des nationalen Luftmessnetzes (BAFU) auf.

    Das NABEL (Nationales Beobachtungsnetz für Luftfremdstoffe) misst seit 1991
    kontinuierlich an 16 Standorten in der Schweiz: NO₂, O₃, PM10, PM2.5,
    SO₂, CO, Russ und weitere Parameter.

    Args:
        params (NabelStationsInput):
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Liste aller NABEL-Stationen mit Kürzel, Name, Kanton und Standorttyp.
             Enthält auch den Link zur BAFU-Datenabfrage.
    """
    stations_list = [
        {
            "kuerzel": code,
            "name": info["name"],
            "kanton": info["canton"],
            "standorttyp": info["type"],
        }
        for code, info in sorted(NABEL_STATIONS.items())
    ]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "nabel_stationen": stations_list,
                "total": len(stations_list),
                "datenabfrage_url": "https://www.bafu.admin.ch/de/datenabfrage-nabel",
                "opendata_swiss": "https://opendata.swiss/de/dataset/nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen",
                "quelle": "BAFU – Nationales Beobachtungsnetz für Luftfremdstoffe (NABEL)",
            },
            ensure_ascii=False,
            indent=2,
        )

    lines = [
        "## NABEL-Messstationen – Nationales Beobachtungsnetz für Luftfremdstoffe\n",
        f"**{len(stations_list)} Messstationen** | Quelle: BAFU\n",
        "| Kürzel | Station | Kanton | Standorttyp |",
        "|--------|---------|--------|-------------|",
    ]
    for s in stations_list:
        lines.append(f"| {s['kuerzel']} | {s['name']} | {s['kanton']} | {s['standorttyp']} |")

    lines += [
        "",
        "**Datenabfrage:** https://www.bafu.admin.ch/de/datenabfrage-nabel",
        "**opendata.swiss:** https://opendata.swiss/de/dataset/nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen",
        "",
        "*Tipp: Für aktuelle Stundenwerte → `env_nabel_current` mit dem Stationskürzel aufrufen.*",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="env_nabel_current",
    annotations={
        "title": "Aktuelle NABEL-Luftqualitätsdaten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_nabel_current(params: NabelCurrentInput) -> str:
    """
    Ruft aktuelle und historische Luftqualitätsdaten einer NABEL-Station ab.

    Liefert Metadaten, Download-Links für Messdaten (CSV) sowie direkte
    Abfrage-URLs für den BAFU-Datenbrowser. Gemessene Parameter: NO₂, O₃,
    PM10, PM2.5, SO₂, CO, Russ (BC).

    Args:
        params (NabelCurrentInput):
            - station: Stationskürzel (z.B. 'ZUE', 'DUB', 'BER')

    Returns:
        str: Stationsinformationen, Messparameter, Datenlinks und Grenzwertkontext.
    """
    code = params.station.upper()
    station_info = NABEL_STATIONS.get(code)

    if not station_info:
        known = ", ".join(sorted(NABEL_STATIONS.keys()))
        return (
            f"Fehler: Station '{code}' nicht gefunden.\n"
            f"Bekannte NABEL-Stationen: {known}\n"
            f"Tipp: `env_nabel_stations` aufrufen für eine vollständige Liste."
        )

    try:
        result = await api.fetch_nabel_data(code, parameter="NO2")
        datasets = result.get("result", {}).get("results", [])
    except Exception as e:
        datasets = []
        api.handle_http_error(e)

    data_url = f"https://www.bafu.admin.ch/de/datenabfrage-nabel?station={code}"
    opendata_url = "https://opendata.swiss/de/organization/bafu"

    lines = [
        f"## NABEL-Station: {station_info['name']} ({code})\n",
        f"- **Kanton:** {station_info['canton']}",
        f"- **Standorttyp:** {station_info['type']}",
        "",
        "### Gemessene Parameter",
        "| Parameter | Einheit | Grenzwert LRV | WHO-Richtwert 2021 |",
        "|-----------|---------|---------------|-------------------|",
        "| NO₂ | µg/m³ | 30 (Jahresmittel) | 10 (Jahresmittel) |",
        "| O₃ | µg/m³ | 100 (Std.-98P) | 60 (Peak-Saison) |",
        "| PM10 | µg/m³ | 20 (Jahresmittel) | 15 (Jahresmittel) |",
        "| PM2.5 | µg/m³ | 10 (Jahresmittel) | 5 (Jahresmittel) |",
        "| SO₂ | µg/m³ | 30 (Jahresmittel) | 40 (24h-Mittel) |",
        "| CO | mg/m³ | 8 (Tagesmittel) | – |",
        "| Russ (BC) | µg/m³ | – | – |",
        "",
        "### Datenzugang",
        f"- **BAFU-Datenabfrage (interaktiv):** {data_url}",
        f"- **opendata.swiss (CSV-Downloads):** {opendata_url}",
        "",
    ]

    if datasets:
        lines += [
            "### Verfügbare Datensätze auf opendata.swiss",
        ]
        for ds in datasets[:3]:
            title = ds.get("title", {})
            name = title.get("de") or title.get("en") or ds.get("name", "")
            lines.append(f"- {name}")

    lines += [
        "",
        "*Tipp: Für eine Grenzwertbewertung eines konkreten Messwerts → `env_air_limits_check` aufrufen.*",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="env_air_limits_check",
    annotations={
        "title": "Luftschadstoff gegen Grenzwerte prüfen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def env_air_limits_check(params: AirLimitsCheckInput) -> str:
    """
    Bewertet einen gemessenen Luftschadstoffwert gegen Schweizer LRV-Grenzwerte
    und WHO 2021-Richtwerte.

    Unterstützte Schadstoffe: NO2, PM10, PM2.5, O3, SO2, CO.
    Grenzwerte gemäss Schweizer Luftreinhalte-Verordnung (LRV, SR 814.318.142.1).

    Args:
        params (AirLimitsCheckInput):
            - pollutant: Schadstoffkürzel ('NO2', 'PM10', 'PM2.5', 'O3', 'SO2', 'CO')
            - value: Gemessener Wert in µg/m³
            - averaging_period: Mittelungszeitraum ('annual', 'daily', 'hourly')

    Returns:
        str: Grenzwert-Vergleich mit Schweizer LRV und WHO 2021, inkl. Überschreitungs-Flag.
    """
    pollutant = params.pollutant.upper()
    if pollutant not in SWISS_LRV_LIMITS and pollutant not in WHO_2021_LIMITS:
        known = ", ".join(sorted(set(list(SWISS_LRV_LIMITS.keys()) + list(WHO_2021_LIMITS.keys()))))
        return f"Fehler: Schadstoff '{pollutant}' nicht erkannt. Unterstützt: {known}"

    assessment = _assess_air_quality(pollutant, params.value)
    return _format_assessment_markdown(assessment)


# --- TOOLS: WASSER / HYDROLOGIE -----------------------------------------------

@mcp.tool(
    name="env_hydro_stations",
    annotations={
        "title": "Hydrologische Messstationen auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def env_hydro_stations(params: HydroStationsInput) -> str:
    """
    Listet hydrologische Messstationen des BAFU an Schweizer Flüssen und Seen auf.

    Das BAFU betreibt ca. 260 Messstationen in der Schweiz. Stationen messen
    Wasserstand (Pegel), Abfluss (m³/s), Wassertemperatur und weitere Parameter
    in einem 10-Minuten-Intervall.

    Args:
        params (HydroStationsInput):
            - canton: Kantonskürzel zum Filtern (z.B. 'ZH')
            - water_body: Gewässername zum Filtern (z.B. 'Limmat')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Stationsliste oder Fehlertext bei API-Problemen.
    """
    try:
        data = await api.fetch_hydro_stations()
    except Exception as e:
        error_msg = api.handle_http_error(e)
        # Fallback: Bekannte Zürcher Stationen als Beispiel
        fallback_stations = [
            {"id": "2099", "name": "Limmat – Zürich/Unterwerk", "canton": "ZH", "water": "Limmat"},
            {"id": "2243", "name": "Sihl – Zürich", "canton": "ZH", "water": "Sihl"},
            {"id": "2490", "name": "Glatt – Rheinsfelden", "canton": "ZH", "water": "Glatt"},
            {"id": "2030", "name": "Rhein – Basel/Rheinhalle", "canton": "BS", "water": "Rhein"},
            {"id": "2008", "name": "Aare – Bern/Schönau", "canton": "BE", "water": "Aare"},
        ]
        lines = [
            f"⚠️ Live-API nicht erreichbar ({error_msg})\n",
            "**Direkter Datenzugang:** https://www.hydrodaten.admin.ch/de/seen-und-fluesse\n",
            "**Beispiel-Stationen für Zürich:**",
            "| Station-ID | Name | Kanton | Gewässer |",
            "|------------|------|--------|---------|",
        ]
        for s in fallback_stations:
            if (not params.canton or params.canton.upper() == s["canton"]) and \
               (not params.water_body or params.water_body.lower() in s["water"].lower()):
                lines.append(f"| {s['id']} | {s['name']} | {s['canton']} | {s['water']} |")
        lines.append("\n*→ Vollständige Stationsliste: https://www.hydrodaten.admin.ch*")
        return "\n".join(lines)

    # Daten verarbeiten
    stations = data if isinstance(data, list) else data.get("stations", data.get("features", []))

    # Filter anwenden
    filtered = []
    for s in stations:
        props = s.get("properties", s)
        canton_val = str(props.get("canton", props.get("kanton", ""))).upper()
        water_val = str(props.get("water_body_name", props.get("water", ""))).lower()

        if params.canton and params.canton.upper() not in canton_val:
            continue
        if params.water_body and params.water_body.lower() not in water_val:
            continue
        filtered.append(props)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "stationen": filtered[:100],
                "total": len(filtered),
                "filter": {"canton": params.canton, "water_body": params.water_body},
                "quelle": "BAFU Hydrodaten – https://www.hydrodaten.admin.ch",
            },
            ensure_ascii=False,
            indent=2,
        )

    lines = [
        f"## Hydrologische Messstationen ({len(filtered)} Resultate)\n",
        f"*Filter: Kanton={params.canton or 'alle'}, Gewässer={params.water_body or 'alle'}*\n",
        "| Station-ID | Name | Kanton | Gewässer |",
        "|------------|------|--------|---------|",
    ]
    for s in filtered[:50]:
        sid = s.get("number", s.get("id", "–"))
        name = s.get("name", "–")
        canton = s.get("canton", s.get("kanton", "–"))
        water = s.get("water_body_name", s.get("water", "–"))
        lines.append(f"| {sid} | {name} | {canton} | {water} |")

    if len(filtered) > 50:
        lines.append(f"\n*…und {len(filtered) - 50} weitere Stationen.*")
    lines.append("\n**Datenportal:** https://www.hydrodaten.admin.ch")
    return "\n".join(lines)


@mcp.tool(
    name="env_hydro_current",
    annotations={
        "title": "Aktuelle Hydrodaten einer Messstation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_hydro_current(params: HydroCurrentInput) -> str:
    """
    Ruft aktuelle Messwerte einer hydrologischen BAFU-Messstation ab.

    Liefert Pegel (m ü.M.), Abfluss (m³/s), Wassertemperatur (°C) sowie
    24h-Min/Max-Werte. Daten werden alle 10 Minuten aktualisiert.

    Bekannte Zürich-relevante Stationen:
      - 2099: Limmat – Zürich/Unterwerk
      - 2243: Sihl – Zürich
      - 2034: Zürichsee – Zürich/Tiefenbrunnen (Pegel)

    Args:
        params (HydroCurrentInput):
            - station_id: BAFU-Stationsnummer (z.B. '2099')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Aktuelle Messwerte inkl. Zeitstempel, oder Fallback mit direktem Link.
    """
    try:
        data = await api.fetch_hydro_station_data(params.station_id)
    except Exception as e:
        error_msg = api.handle_http_error(e)
        portal_url = f"https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{params.station_id}"
        return (
            f"⚠️ Aktuelle Daten für Station {params.station_id} nicht abrufbar: {error_msg}\n\n"
            f"**Direktzugang:** {portal_url}\n"
            f"**Vollständiges Datenportal:** https://www.hydrodaten.admin.ch/de"
        )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {"station_id": params.station_id, "daten": data,
             "quelle": "BAFU Hydrodaten"},
            ensure_ascii=False, indent=2,
        )

    # Werte extrahieren (flexible Struktur je nach API-Version)
    name = data.get("name", data.get("station_name", f"Station {params.station_id}"))
    water = data.get("water_body_name", data.get("water", "–"))
    timestamp = data.get("datetime", data.get("timestamp", "–"))

    params_data = data.get("parameters", data.get("measurements", []))

    lines = [
        f"## Hydrologische Daten: {name} (Station {params.station_id})\n",
        f"- **Gewässer:** {water}",
        f"- **Zeitstempel:** {timestamp}",
        "",
        "### Aktuelle Messwerte",
        "| Parameter | Aktuell | Min 24h | Mittel 24h | Max 24h |",
        "|-----------|---------|---------|------------|---------|",
    ]

    if isinstance(params_data, list):
        for p in params_data:
            p_name = p.get("name", p.get("parameter", "–"))
            val = p.get("value", p.get("current", "–"))
            unit = p.get("unit", "")
            min24 = p.get("min-24h", p.get("min_24h", "–"))
            mean24 = p.get("mean-24h", p.get("mean_24h", "–"))
            max24 = p.get("max-24h", p.get("max_24h", "–"))
            lines.append(f"| {p_name} {unit} | **{val}** | {min24} | {mean24} | {max24} |")
    else:
        lines.append("| – | Keine Parameterdaten verfügbar | – | – | – |")

    lines += [
        "",
        f"**Detailansicht:** https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{params.station_id}",
        "",
        "*Tipp: Für historische Daten → `env_hydro_history` aufrufen.*",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="env_hydro_history",
    annotations={
        "title": "Historische Hydrodaten einer Messstation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def env_hydro_history(params: HydroHistoryInput) -> str:
    """
    Ruft historische Stundenwerte einer BAFU-Hydromesstations ab.

    Ermöglicht zeitliche Analysen von Wasserstand, Abfluss und Temperatur
    über bis zu 30 Tage. Ideal für Trendanalysen und Extremereignis-Recherche.

    Args:
        params (HydroHistoryInput):
            - station_id: BAFU-Stationsnummer
            - parameter: 'Abfluss', 'Pegel' oder 'Temperatur'
            - days: Anzahl Tage (1–30)

    Returns:
        str: Link zu historischen Daten und Hinweise zum Datenzugang.
    """
    try:
        result = await api.fetch_hydro_station_history(
            params.station_id, params.parameter, params.days
        )
        raw = result.get("raw", "")
    except Exception as e:
        raw = ""
        api.handle_http_error(e)

    # Direktlinks für historische Daten
    portal_url = f"https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{params.station_id}"
    chart_url = f"https://www.hydrodaten.admin.ch/graphs/{params.station_id}/{params.parameter.lower()}_7days.png"

    lines = [
        f"## Historische Hydrodaten: Station {params.station_id}\n",
        f"- **Parameter:** {params.parameter}",
        f"- **Zeitraum:** letzte {params.days} Tage",
        "",
        "### Datenzugang",
        f"- **Interaktives Portal:** {portal_url}",
        f"- **7-Tage-Grafik:** {chart_url}",
        "- **Langzeitdaten (opendata.swiss):** https://opendata.swiss/de/organization/bafu",
        "",
    ]

    if raw:
        # Rohdaten kurz zusammenfassen (CSV-Preview)
        lines_raw = raw.strip().split("\n")
        preview = lines_raw[:5]
        lines += [
            f"### Datenvorschau (erste {len(preview)} Zeilen)",
            "```",
            *preview,
            "```",
            f"\n*Gesamte Daten: {len(lines_raw)} Zeilen*",
        ]

    lines += [
        "",
        "**Tipp für historische Längsschnittanalysen:**",
        "Die BAFU-Hydrologie-Abteilung stellt Tagesmittelwerte ab 1900 via opendata.swiss als CSV zur Verfügung.",
        "→ https://opendata.swiss/de/dataset?q=hydrologie+tages",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="env_flood_warnings",
    annotations={
        "title": "Aktuelle Hochwasserwarnungen Schweiz",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_flood_warnings(params: FloodWarningsInput) -> str:
    """
    Ruft aktuelle Hochwasserwarnungen aller BAFU-Messstationen in der Schweiz ab.

    Das BAFU gibt Hochwasserwarnungen in 5 Gefahrenstufen aus:
    1=Keine, 2=Mässig, 3=Erheblich, 4=Gross, 5=Sehr gross.

    Args:
        params (FloodWarningsInput):
            - min_level: Minimale Gefahrenstufe (Standard: 2)
            - canton: Kantonskürzel zum Filtern

    Returns:
        str: Aktuell aktive Hochwasserwarnungen, gefiltert nach Gefahrenstufe und Kanton.
    """
    try:
        data = await api.fetch_hydro_warnings()
        stations = data if isinstance(data, list) else data.get("stations", [])

        # Filter
        warnings = []
        for s in stations:
            props = s.get("properties", s)
            level = int(props.get("warning_level", props.get("gefahrenstufe", 1)))
            canton = str(props.get("canton", props.get("kanton", ""))).upper()

            if level < params.min_level:
                continue
            if params.canton and params.canton.upper() != canton:
                continue
            warnings.append({**props, "parsed_level": level})

        # Sortieren nach Gefahrenstufe absteigend
        warnings.sort(key=lambda x: x["parsed_level"], reverse=True)

        if not warnings:
            return (
                f"✅ **Keine aktiven Hochwasserwarnungen** "
                f"(Stufe ≥ {params.min_level}"
                f"{', Kanton ' + params.canton if params.canton else ''}).\n\n"
                f"**Aktuelle Übersicht:** https://www.hydrodaten.admin.ch/de/hochwasserwarnungen"
            )

        lines = [
            f"## ⚠️ Aktive Hochwasserwarnungen ({len(warnings)} Stationen)\n",
            f"*Filter: Stufe ≥ {params.min_level}"
            f"{', Kanton ' + params.canton if params.canton else ''}*\n",
            "| Station | Gewässer | Kanton | Gefahrenstufe |",
            "|---------|---------|--------|---------------|",
        ]
        for w in warnings:
            name = w.get("name", "–")
            water = w.get("water_body_name", w.get("water", "–"))
            c = w.get("canton", w.get("kanton", "–"))
            level = w["parsed_level"]
            level_text = _format_flood_level(level)
            lines.append(f"| {name} | {water} | {c} | {level_text} |")

        lines += [
            "",
            "**Gefahrenstufen:** 1=Keine | 2=Mässig | 3=Erheblich | 4=Gross | 5=Sehr gross",
            "**Quelle:** https://www.hydrodaten.admin.ch/de/hochwasserwarnungen",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Warnungsdaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang zu aktuellen Warnungen:**\n"
            "- https://www.hydrodaten.admin.ch/de/hochwasserwarnungen\n"
            "- https://www.naturgefahren.ch (Übersichtsseite Naturgefahren)"
        )


# --- TOOLS: NATURGEFAHREN -----------------------------------------------------

@mcp.tool(
    name="env_hazard_overview",
    annotations={
        "title": "Naturgefahren-Bulletin Schweiz",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_hazard_overview(params: HazardOverviewInput) -> str:
    """
    Ruft das aktuelle Naturgefahren-Bulletin für die Schweiz ab.

    Das Bulletin wird täglich vom Institut für Schnee- und Lawinenforschung (SLF)
    und BAFU herausgegeben und umfasst: Hochwasser, Lawinen, Steinschlag,
    Rutschungen und Sturm.

    Args:
        params (HazardOverviewInput):
            - language: Sprache ('de', 'fr', 'it', 'en')

    Returns:
        str: Aktuelles Naturgefahren-Bulletin inkl. direkter Links.
    """
    try:
        data = await api.fetch_hazard_overview(params.language)

        lines = [
            "## 🏔️ Naturgefahren-Bulletin Schweiz\n",
            f"*Sprache: {params.language} | Quelle: naturgefahren.ch (SLF/BAFU)*\n",
        ]

        # Gefahrentypen verarbeiten
        hazards = data.get("warnings", data.get("dangers", []))
        if hazards:
            lines += ["### Aktuelle Gefahrenübersicht", ""]
            for h in hazards:
                htype = h.get("type", h.get("hazard_type", "–"))
                level = h.get("danger_level", h.get("level", "–"))
                desc = h.get("text", h.get("description", ""))
                lines.append(f"**{htype}** – Gefahrenstufe {level}")
                if desc:
                    lines.append(f"  {desc[:200]}")
                lines.append("")
        else:
            lines.append("*Keine spezifischen Warnungen in den API-Daten.*")

        lines += [
            "### Direkte Links",
            "- **naturgefahren.ch:** https://www.naturgefahren.ch",
            "- **Lawinenbulletin (SLF):** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/",
            "- **Hochwasserwarnung:** https://www.hydrodaten.admin.ch/de/hochwasserwarnungen",
            "- **Waldbrandgefahr:** https://www.waldbrandgefahr.ch",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Bulletin nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:**\n"
            "- https://www.naturgefahren.ch\n"
            "- https://www.slf.ch/de/lawinenbulletin-und-schneesituation/\n"
            "- https://www.hydrodaten.admin.ch/de/hochwasserwarnungen\n"
            "- https://www.waldbrandgefahr.ch\n"
        )


@mcp.tool(
    name="env_hazard_regions",
    annotations={
        "title": "Regionsspezifische Naturgefahrenwarnungen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_hazard_regions(params: HazardRegionsInput) -> str:
    """
    Ruft regionsspezifische Naturgefahrenwarnungen ab.

    Ermöglicht gezielte Abfragen für Schulausflüge, Events oder
    Infrastrukturplanung in einem spezifischen Gebiet der Schweiz.

    Args:
        params (HazardRegionsInput):
            - region: Regionsname (z.B. 'Zürich', 'Graubünden', 'Wallis')
            - hazard_type: Gefahrentyp ('hochwasser', 'lawinen', 'steinschlag', 'rutschungen')
            - language: Sprache

    Returns:
        str: Warnungen für die angegebene Region inkl. Links zu Karten.
    """
    try:
        data = await api.fetch_regional_hazards(params.region, params.language)

        lines = [
            "## 🗺️ Regionale Naturgefahrenwarnungen\n",
            f"*Region: {params.region or 'Gesamte Schweiz'}"
            f"{', Typ: ' + params.hazard_type if params.hazard_type else ''}*\n",
        ]

        regions_data = data.get("regions", data.get("warnings", []))

        if not regions_data:
            lines.append("*Keine spezifischen Warnungen für diese Region.*")
        else:
            for region in regions_data[:20]:
                r_name = region.get("name", region.get("region", "–"))
                if params.region and params.region.lower() not in r_name.lower():
                    continue
                warnings = region.get("warnings", [region])
                for w in warnings:
                    htype = w.get("type", w.get("hazard_type", "–"))
                    if params.hazard_type and params.hazard_type.lower() not in htype.lower():
                        continue
                    level = w.get("danger_level", "–")
                    lines.append(f"- **{r_name}** | {htype}: Stufe {level}")

        lines += [
            "",
            "**Interaktive Karte:** https://www.naturgefahren.ch",
            "**Gefahrenkarten BAFU:** https://map.bafu.admin.ch/?topic=bafu&lang=de",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Regionaldaten nicht abrufbar: {error_msg}\n\n"
            "**Manuelle Abfrage:**\n"
            "- https://www.naturgefahren.ch\n"
            "- https://map.bafu.admin.ch (BAFU GIS – Gefahrenkarten)\n"
        )


@mcp.tool(
    name="env_wildfire_danger",
    annotations={
        "title": "Waldbrandgefahr Schweiz",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def env_wildfire_danger(params: WildfireDangerInput) -> str:
    """
    Ruft den aktuellen Waldbrandgefahren-Index nach Regionen ab.

    Die Waldbrandgefahr wird täglich durch das BAFU berechnet und auf
    einer 5-stufigen Skala (gering bis sehr gross) kommuniziert.
    Relevant für Schulausflüge, Events und Forstbetriebe.

    Args:
        params (WildfireDangerInput):
            - language: 'de', 'fr', 'it'
            - canton: Kantonskürzel zum Filtern

    Returns:
        str: Aktuelle Waldbrandgefahr nach Regionen/Kantonen.
    """
    try:
        data = await api.fetch_wildfire_danger(params.language)

        regions = data.get("regions", data.get("danger_zones", []))

        lines = [
            "## 🔥 Waldbrandgefahr Schweiz\n",
            f"*Sprache: {params.language} | Quelle: waldbrandgefahr.ch (BAFU)*\n",
            "**Gefahrenstufen:** 1=Gering | 2=Mässig | 3=Erheblich | 4=Gross | 5=Sehr gross\n",
        ]

        if regions:
            lines += [
                "| Region | Kanton | Gefahrenstufe | Status |",
                "|--------|--------|---------------|--------|",
            ]
            for r in regions:
                canton = str(r.get("canton", r.get("kanton", "–"))).upper()
                if params.canton and params.canton.upper() != canton:
                    continue
                name = r.get("name", r.get("region", canton))
                level = int(r.get("danger_level", r.get("level", 0)))
                level_info = WILDFIRE_DANGER_LEVELS.get(level, {"label": "–", "color": "–"})
                icon = "🟢" if level <= 1 else ("🟡" if level == 2 else ("🟠" if level == 3 else "🔴"))
                lines.append(f"| {name} | {canton} | {icon} Stufe {level} | {level_info['label']} |")
        else:
            lines.append("*Keine Regionaldaten verfügbar.*")

        lines += [
            "",
            "**Aktuelle Gefahrenkarte:** https://www.waldbrandgefahr.ch/de/aktuelle-lage",
            "**Verhaltensregeln bei Waldbrandgefahr:** https://www.bafu.admin.ch/de/themen/wald/waldbrand",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Waldbranddaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:**\n"
            "- https://www.waldbrandgefahr.ch/de/aktuelle-lage\n"
            "- https://www.naturgefahren.ch\n"
        )


# --- TOOLS: UMWELTDATEN / BAFU-DATENKATALOG -----------------------------------

@mcp.tool(
    name="env_bafu_datasets",
    annotations={
        "title": "BAFU-Datensätze auf opendata.swiss suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def env_bafu_datasets(params: BafuDatasetsInput) -> str:
    """
    Sucht BAFU-Datensätze auf dem Schweizer Open-Data-Portal opendata.swiss.

    Das BAFU publiziert Datensätze zu Luft, Wasser, Boden, Biodiversität,
    Lärm, Klima, Wald und weiteren Umweltthemen als offene Daten (OGD).
    Ergebnisse enthalten Titel, Beschreibung und Download-URLs (CSV, JSON, WMS).

    Args:
        params (BafuDatasetsInput):
            - query: Suchbegriff ('Luftqualität', 'Hochwasser', 'NABEL', etc.)
            - rows: Anzahl Resultate (1–50)
            - offset: Offset für Paginierung

    Returns:
        str: Liste der BAFU-Datensätze mit Kurzbeschreibung und Links.
    """
    try:
        data = await api.search_bafu_datasets(params.query, params.rows, params.offset)
        result = data.get("result", {})
        total = result.get("count", 0)
        datasets = result.get("results", [])

        lines = [
            "## BAFU-Datensätze auf opendata.swiss\n",
            f"**{total} Datensätze gefunden** | Suche: '{params.query or 'alle BAFU-Datensätze'}'",
            f"*Zeige {params.offset + 1}–{params.offset + len(datasets)} von {total}*\n",
        ]

        for ds in datasets:
            title = ds.get("title", {})
            name = title.get("de") or title.get("fr") or title.get("en") or ds.get("name", "–")
            desc = ds.get("notes", {})
            if isinstance(desc, dict):
                desc_text = desc.get("de") or desc.get("en") or ""
            else:
                desc_text = str(desc)
            desc_text = desc_text[:150] + "…" if len(desc_text) > 150 else desc_text

            slug = ds.get("name", "")
            url = f"https://opendata.swiss/de/dataset/{slug}" if slug else "–"
            modified = ds.get("metadata_modified", "–")[:10]

            lines += [
                f"### {name}",
                f"*Aktualisiert: {modified}*",
                desc_text,
                f"→ {url}",
                "",
            ]

        if total > params.offset + len(datasets):
            next_offset = params.offset + params.rows
            lines.append(
                f"*Weitere Datensätze: `env_bafu_datasets` mit offset={next_offset} aufrufen.*"
            )

        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Datensatzsuche fehlgeschlagen: {error_msg}\n\n"
            "**Direktzugang zum BAFU-Datenkatalog:**\n"
            "- https://opendata.swiss/de/organization/bafu\n"
            "- https://www.bafu.admin.ch/de/daten\n"
        )


@mcp.tool(
    name="env_bafu_dataset_detail",
    annotations={
        "title": "BAFU-Datensatz Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def env_bafu_dataset_detail(params: BafuDatasetDetailInput) -> str:
    """
    Ruft vollständige Metadaten und Download-URLs eines BAFU-Datensatzes ab.

    Liefert: Titel, Beschreibung, Ressourcen mit Direktlinks (CSV, JSON, WMS/WFS),
    Lizenz, Aktualisierungsintervall und Kontaktinformationen.

    Args:
        params (BafuDatasetDetailInput):
            - dataset_id: Dataset-ID oder Slug (z.B. 'nabel-luftqualitaet-stationen')

    Returns:
        str: Vollständige Metadaten inkl. aller Download-Ressourcen.
    """
    try:
        data = await api.get_bafu_dataset(params.dataset_id)
        result = data.get("result", {})

        title = result.get("title", {})
        name = title.get("de") or title.get("en") or result.get("name", "–")
        desc = result.get("notes", {})
        desc_text = (desc.get("de") or desc.get("en") or "") if isinstance(desc, dict) else str(desc)
        license_val = result.get("license_title", result.get("license_id", "–"))
        modified = result.get("metadata_modified", "–")[:10]
        frequency = result.get("accrual_periodicity", "–")
        resources = result.get("resources", [])

        lines = [
            f"## {name}\n",
            f"- **Lizenz:** {license_val}",
            f"- **Aktualisierung:** {frequency}",
            f"- **Zuletzt geändert:** {modified}",
            "",
            "### Beschreibung",
            desc_text[:500] + ("…" if len(desc_text) > 500 else ""),
            "",
            f"### Ressourcen ({len(resources)})",
        ]

        for r in resources:
            r_name = r.get("name", {})
            r_label = (r_name.get("de") or r_name.get("en") or "") if isinstance(r_name, dict) else str(r_name)
            r_format = r.get("format", "–")
            r_url = r.get("download_url", r.get("url", "–"))
            lines.append(f"- **{r_label}** ({r_format}): {r_url}")

        lines += [
            "",
            f"**opendata.swiss:** https://opendata.swiss/de/dataset/{params.dataset_id}",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = api.handle_http_error(e)
        return (
            f"⚠️ Datensatz '{params.dataset_id}' nicht gefunden: {error_msg}\n\n"
            "**Tipp:** Nutze `env_bafu_datasets` um gültige Dataset-IDs zu finden.\n"
            "**BAFU-Datenkatalog:** https://opendata.swiss/de/organization/bafu"
        )


# --- Resources ----------------------------------------------------------------

@mcp.resource("env://grenzwerte/luft")
async def get_air_limits() -> str:
    """Schweizer LRV-Grenzwerte und WHO 2021-Richtwerte für Luftschadstoffe."""
    data = {
        "schweizer_lrv": {
            k: {"wert": v, "einheit": "µg/m³"}
            for k, v in SWISS_LRV_LIMITS.items()
        },
        "who_2021": {
            k: {"wert": v, "einheit": "µg/m³"}
            for k, v in WHO_2021_LIMITS.items()
        },
        "rechtsgrundlage": "Luftreinhalte-Verordnung (LRV), SR 814.318.142.1",
        "quelle_who": "WHO Global Air Quality Guidelines 2021",
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.resource("env://nabel/stationen")
async def get_nabel_stations_resource() -> str:
    """Vollständige NABEL-Stationsliste als strukturierte JSON-Ressource."""
    return json.dumps(
        {
            "stationen": NABEL_STATIONS,
            "total": len(NABEL_STATIONS),
            "quelle": "BAFU – Nationales Beobachtungsnetz für Luftfremdstoffe",
            "url": "https://www.bafu.admin.ch/de/themen/luft/nabel",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("env://hochwasser/gefahrenstufen")
async def get_flood_levels_resource() -> str:
    """Hochwasser-Gefahrenstufen 1–5 mit Beschreibungen."""
    return json.dumps(
        {"gefahrenstufen": FLOOD_DANGER_LEVELS, "quelle": "BAFU Hydrodaten"},
        ensure_ascii=False,
        indent=2,
    )


# --- Entry Point --------------------------------------------------------------

def main() -> None:
    port = int(os.environ.get("PORT", 8000))
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "streamable_http":
        mcp.run(transport="streamable_http", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
