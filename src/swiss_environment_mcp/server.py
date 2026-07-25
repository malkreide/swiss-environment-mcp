"""
Swiss Environment MCP Server

MCP-Server für Schweizer Umweltdaten des BAFU (Bundesamt für Umwelt) und SLF.
Bietet 18 Tools in 6 thematischen Clustern:

  Luft (3):        env_nabel_stations, env_nabel_current, env_air_limits_check
  Wasser (5):      env_hydro_stations, env_hydro_current, env_hydro_history,
                   env_flood_warnings, env_bathing_water
  Naturgefahren (3): env_hazard_overview, env_hazard_regions, env_wildfire_danger
  Schnee/SLF (3):  env_snow_stations, env_snow_current, env_avalanche_bulletin
  Jagd (2):        env_hunting_species, env_hunting_stats
  Umweltdaten (2): env_bafu_datasets, env_bafu_dataset_detail

Datenquellen:
  - BAFU NABEL (Nationale Luftmessstation-Daten)
  - LINDAS SPARQL (aktuelle Hydrologiedaten, lindas.admin.ch)
  - hydrodaten.admin.ch (Hydrologische Messdaten, REST-Fallback)
  - naturgefahren.ch (Naturgefahren-Bulletin SLF/BAFU)
  - waldbrandgefahr.ch (Waldbrandgefahren-Index)
  - SLF-Datenservice (Schnee/Lawinen: measurement-api.slf.ch, aws.slf.ch)
  - jagdstatistik.ch (Eidg. Jagdstatistik, BAFU)
  - opendata.swiss CKAN (BAFU-Datenkatalog)

Alle Daten: öffentlich, keine Authentifizierung erforderlich.
Lizenz der Quelldaten: BAFU-Nutzungsbedingungen / Open Government Data (OGD)
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import api_client as api
from .lindas import cube as lindas_cube
from .logging_setup import configure_logging, get_logger
from .tracing import configure_tracing, trace_tool

# --- Konfiguration ------------------------------------------------------------


class Settings(BaseSettings):
    """Server-Konfiguration. Transport-agnostisch, via Env-Vars (Audit ARCH-004).

    Default-Host ist 127.0.0.1 (Audit SEC-016 — kein 0.0.0.0-Default).
    Im Container wird MCP_HOST=0.0.0.0 explizit gesetzt (Dockerfile/render.yaml).
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    mcp_transport: str = "stdio"  # "stdio" | "streamable-http"
    mcp_host: str = "127.0.0.1"
    port: int = 8000
    # CORS-Origins für den HTTP-Transport (Audit SDK-004). Komma-separiert.
    # Default "*" für Dev; in Produktion auf eine explizite Liste setzen.
    mcp_cors_allow_origins: str = "*"

    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.mcp_cors_allow_origins.split(",") if o.strip()]


settings = Settings()

# Strukturiertes Logging nach stderr initialisieren (Audit OBS-003/OBS-004).
configure_logging()
logger = get_logger(server="swiss-environment-mcp")

# OpenTelemetry-Tracing initialisieren (Audit OBS-006). No-op ohne OTLP-Endpoint.
configure_tracing()


async def _handle_tool_error(
    tool: str, exc: Exception, ctx: Context | None = None, **fields: object
) -> str:
    """Zentrale Fehlerbehandlung für Tools (Audit OBS-001/OBS-002/SDK-003).

    - Liefert eine maskierte, user-freundliche Meldung (keine Internals ans LLM).
    - Loggt die echten Fehlerdetails strukturiert nach stderr (Server-Log).
    - Meldet den Fehler zusätzlich über den MCP-Context (ctx.warning), falls vorhanden.
    """
    msg = api.handle_http_error(exc)
    logger.warning(
        "tool_error",
        tool=tool,
        error_type=type(exc).__name__,
        detail=str(exc),
        **fields,
    )
    if ctx is not None:
        try:
            await ctx.warning(f"{tool}: {msg}")
        except Exception:  # ctx-Logging darf den Tool-Call nie zum Absturz bringen
            pass
    return msg


def _terminal_failure(message: str) -> ToolError:
    """Signalisiert einen terminalen Ausführungsfehler als MCP `isError:true` (OBS-001).

    Wird via `raise` genutzt: FastMCP setzt daraufhin `isError=true` im
    CallToolResult (statt einen Fehlertext als reguläres, erfolgreiches Resultat
    zurückzugeben). Die enthaltenen Direktlinks/Recovery-Hinweise bleiben im
    Fehler-Content erhalten — der Client bekommt weiterhin die Hilfestellung,
    weiss aber jetzt maschinenlesbar, dass der Abruf fehlgeschlagen ist.

    Nur für echte Ausführungsfehler (Upstream nicht erreichbar, Egress
    blockiert) — NICHT für Graceful-Degradation-Pfade, die genuine
    Ersatzdaten liefern (z.B. Beispiel-Stationslisten), oder für leere, aber
    gültige Resultate (match_type "none", "keine aktive Warnung").
    """
    return ToolError(message)


# --- Konstanten ---------------------------------------------------------------

# Grenzwerte gemäss Luftreinhalte-Verordnung (LRV) Schweiz, µg/m³
SWISS_LRV_LIMITS: dict[str, float] = {
    "NO2": 30.0,  # Jahresmittelwert
    "PM10": 20.0,  # Jahresmittelwert (WHO 2021: 15)
    "PM2.5": 10.0,  # Jahresmittelwert (WHO 2021: 5)
    "O3": 100.0,  # Stundenmittelwert 98-Perzentil
    "SO2": 30.0,  # Jahresmittelwert
    "CO": 8000.0,  # Tagesmittelwert
}

# WHO 2021 Richtwerte, µg/m³
WHO_2021_LIMITS: dict[str, float] = {
    "NO2": 10.0,
    "PM10": 15.0,
    "PM2.5": 5.0,
    "O3": 60.0,  # Jahresmittelwert peak season
    "SO2": 40.0,  # 24-Stunden-Mittelwert
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
    1: {"label": "Keine Gefahr", "color": "grün", "description": "Normaler Wasserstand"},
    2: {
        "label": "Mässige Gefahr",
        "color": "gelb",
        "description": "Erhöhter Wasserstand, lokale Überschwemmungen möglich",
    },
    3: {
        "label": "Erhebliche Gefahr",
        "color": "orange",
        "description": "Bedeutende Überschwemmungen",
    },
    4: {"label": "Grosse Gefahr", "color": "rot", "description": "Grosse Überschwemmungen"},
    5: {
        "label": "Sehr grosse Gefahr",
        "color": "lila",
        "description": "Katastrophale Überschwemmungen",
    },
}

# Waldbrand-Gefahrenstufen
WILDFIRE_DANGER_LEVELS: dict[int, dict[str, str]] = {
    1: {"label": "Gering", "color": "grün"},
    2: {"label": "Mässig", "color": "gelb"},
    3: {"label": "Erheblich", "color": "orange"},
    4: {"label": "Gross", "color": "rot"},
    5: {"label": "Sehr gross", "color": "dunkelrot"},
}

# Lawinen-Gefahrenstufen (europäische EAWS-Skala 1–5)
AVALANCHE_DANGER_LEVELS: dict[int, dict[str, str]] = {
    1: {"label": "Gering", "color": "grün"},
    2: {"label": "Mässig", "color": "gelb"},
    3: {"label": "Erheblich", "color": "orange"},
    4: {"label": "Gross", "color": "rot"},
    5: {"label": "Sehr gross", "color": "schwarz/rot"},
}

# EAWS-Textwerte (CAAML `mainValue`) → numerische Stufe.
_AVALANCHE_WORD_TO_LEVEL: dict[str, int] = {
    "low": 1,
    "moderate": 2,
    "considerable": 3,
    "high": 4,
    "very_high": 5,
    "very high": 5,
}

# --- Jagdstatistik-Lookups (statisch, aus Live-Probe 2026-07-19 geharvestet) ---
# Stabile Dimensionen werden eingebettet; die volatilen Zahlen live abgefragt
# (siehe docs/probe-jagdstatistik.md, «Architektur-Entscheid»).

# Datentyp `th`
JAGD_DATATYPES: dict[str, str] = {
    "abschuss": "1",
    "bestand": "2",
    "aussetzung": "3",
    "fallwild": "4",
}

# Kanton `ar` (CH = ganze Schweiz + 26 Kantone)
JAGD_CANTONS: dict[str, str] = {
    "CH": "Ganze Schweiz",
    "AG": "Aargau",
    "AR": "Appenzell A.Rh.",
    "AI": "Appenzell I.Rh.",
    "BS": "Basel Stadt",
    "BL": "Baselland",
    "BE": "Bern",
    "FR": "Freiburg",
    "GE": "Genf",
    "GL": "Glarus",
    "GR": "Graubünden",
    "JU": "Jura",
    "LU": "Luzern",
    "NE": "Neuenburg",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SH": "Schaffhausen",
    "SZ": "Schwyz",
    "SO": "Solothurn",
    "SG": "St. Gallen",
    "TI": "Tessin",
    "TG": "Thurgau",
    "UR": "Uri",
    "VD": "Waadt",
    "VS": "Wallis",
    "ZG": "Zug",
    "ZH": "Zürich",
}

# Tierart `sp`-Code → Name (36 Arten)
JAGD_SPECIES: dict[str, str] = {
    "2": "Reh",
    "1": "Rothirsch",
    "3": "Gämse",
    "7": "Wildschwein",
    "4": "Steinbock",
    "8": "Mufflon",
    "5": "Sikahirsch",
    "6": "Damhirsch",
    "401": "Jagdbare Huftiere",
    "15": "Rotfuchs",
    "16": "Dachs",
    "18": "Baummarder",
    "17": "Steinmarder",
    "28": "Bär",
    "21": "Fischotter",
    "29": "Goldschakal",
    "20": "Hermelin / Mauswiesel",
    "19": "Iltis",
    "26": "Mauswiesel",
    "22": "Luchs",
    "23": "Wildkatze",
    "27": "Wolf",
    "50": "Marderhund",
    "51": "Waschbär",
    "402": "Raubtiere",
    "30": "Feldhase",
    "31": "Schneehase",
    "32": "Wildkaninchen",
    "33": "Murmeltier",
    "55": "Biber",
    "34": "Eichhörnchen",
    "52": "Bisamratte",
    "53": "Nutria",
    "37": "Baumwollschwanzkaninchen",
    "35": "Grauhörnchen",
    "36": "Streifenhörnchen",
}


def _resolve_species(value: str) -> str | None:
    """Löst eine Tierart-Eingabe (Code oder Name) zu einem `sp`-Code auf."""
    v = value.strip()
    if v in JAGD_SPECIES:
        return v
    low = v.lower()
    for code, name in JAGD_SPECIES.items():
        if name.lower() == low:
            return code
    for code, name in JAGD_SPECIES.items():  # Teilstring-Fallback
        if low and low in name.lower():
            return code
    return None


# --- Server-Initialisierung ---------------------------------------------------


def _mcp_protocol_version() -> str:
    """Vom SDK unterstützte MCP-Protokollversion (Audit ARCH-012).

    Best-effort: Über die tatsächlich pro Session ausgehandelte Version hinaus
    verankert dies den Spec-Stand des gepinnten SDK im Server-Log — ein
    Minor-SDK-Update, das die Protokollversion verschiebt, wird so im Log
    (und damit im Audit-Trail) sichtbar.
    """
    try:
        from mcp.types import LATEST_PROTOCOL_VERSION

        return str(LATEST_PROTOCOL_VERSION)
    except Exception:  # pragma: no cover - SDK-Layout-Änderung
        return "unknown"


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Gemeinsames Lifecycle-Management für alle Transports (Audit SDK-001).

    Erzeugt den geteilten HTTP-Client beim Start und schliesst ihn beim
    Shutdown — statt pro Tool-Call einen neuen Client zu öffnen. Loggt beim
    Start die unterstützte MCP-Protokollversion (Audit ARCH-012).
    """
    logger.info(
        "server_start",
        transport=settings.mcp_transport,
        mcp_protocol_version=_mcp_protocol_version(),
    )
    await api.startup()
    try:
        yield
    finally:
        await api.shutdown()


mcp = FastMCP(
    "swiss_environment_mcp",
    instructions="""
    MCP-Server für Schweizer Umweltdaten des BAFU.
    Bietet Zugriff auf Luftqualität (NABEL), Hydrologiedaten (Flüsse/Seen),
    Hochwasserwarnungen, Naturgefahren-Bulletin und Waldbrandgefahr.
    Alle Daten stammen von Schweizer Bundesbehörden und sind öffentlich zugänglich.
    Zeitzone: Schweiz (CET/CEST). Masseinheiten: µg/m³ (Luft), m (Pegel), m³/s (Abfluss).
    """,
    lifespan=lifespan,
    host=settings.mcp_host,
    port=settings.port,
)


# --- Health-Endpoint (für Cloud-Load-Balancer, Audit SCALE-004/SEC-016) -------


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Liveness-Check für Render/Railway (render.yaml: healthCheckPath: /health)."""
    return JSONResponse({"status": "ok", "service": "swiss-environment-mcp"})


# --- Pydantic-Eingabemodelle --------------------------------------------------


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


# Match-Typ für Such-/Listen-Resultate (Audit ARCH-003).
MatchType = Literal["exact", "fuzzy", "none"]


class ResponseEnvelope(BaseModel):
    """Konsistenter Response-Envelope für Such-/Listen-Tools (Audit SDK-002).

    Markdown bleibt das menschenlesbare Default-Format; der JSON-Modus liefert
    diesen typisierten Envelope mit Quelle, Provenance, Count und match_type.
    """

    source: str
    provenance: str
    count: int
    match_type: MatchType = "exact"
    results: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None
    query: dict[str, Any] | None = None


def _envelope_json(
    *,
    source: str,
    provenance: str,
    results: list[dict[str, Any]],
    match_type: MatchType = "exact",
    note: str | None = None,
    query: dict[str, Any] | None = None,
) -> str:
    """Serialisiert einen ResponseEnvelope als JSON-String (Audit SDK-002)."""
    envelope = ResponseEnvelope(
        source=source,
        provenance=provenance,
        count=len(results),
        match_type=match_type,
        results=results,
        note=note,
        query=query,
    )
    return envelope.model_dump_json(indent=2, exclude_none=True)


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
        pattern=r"^[A-Za-z]{2,10}$",  # Whitelist (SEC-018)
        strict=True,
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
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
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
        pattern=r"^[0-9]{2,10}$",  # Whitelist: nur Ziffern (SEC-018)
        strict=True,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class HydroHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str = Field(
        ...,
        description="BAFU-Stationsnummer",
        min_length=2,
        max_length=10,
        pattern=r"^[0-9]{2,10}$",  # Whitelist: nur Ziffern (SEC-018)
        strict=True,
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
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class BathingWaterInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    location: str = Field(
        default="",
        description="Badestellen-Name zum Suchen (Teilstring, z.B. 'Mythenquai', 'Clendy') – leer = Übersicht",
        max_length=60,
    )
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'ZH', 'VD') – leer = alle",
        max_length=2,
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
    )
    limit: int = Field(
        default=12,
        description="Maximale Anzahl Messwerte bzw. Badestellen (1–50)",
        ge=1,
        le=50,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


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
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
    )


class SnowStationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'GR', 'VS', 'BE') – leer = alle",
        max_length=2,
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SnowCurrentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    canton: str = Field(
        default="",
        description="Kantonskürzel zum Filtern (z.B. 'GR', 'VS') – leer = ganze Schweiz",
        max_length=2,
        pattern=r"^[A-Za-z]{0,2}$",  # Whitelist (SEC-018)
        strict=True,
    )
    station: str = Field(
        default="",
        description="IMIS-Stationscode zum Filtern (z.B. 'DAV2') – leer = alle",
        max_length=10,
        pattern=r"^[A-Za-z0-9]{0,10}$",  # Whitelist (SEC-018)
        strict=True,
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Stationen in der Ausgabe (1–100)",
        ge=1,
        le=100,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AvalancheBulletinInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    language: str = Field(
        default="de",
        description="Sprache: 'de', 'fr', 'it', 'en'",
        max_length=2,
        pattern=r"^[a-z]{2}$",  # Whitelist (SEC-018)
    )
    region: str = Field(
        default="",
        description="Regionsname/-code zum Filtern (Teilstring) – leer = alle Warnregionen",
        max_length=60,
    )


class HuntingSpeciesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class HuntingStatsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    species: str = Field(
        ...,
        description="Tierart als Name oder sp-Code (z.B. 'Reh', 'Rothirsch', '2')",
        min_length=1,
        max_length=40,
        pattern=r"^[A-Za-zÀ-ÿ0-9 /]{1,40}$",  # Whitelist (SEC-018)
    )
    canton: str = Field(
        default="CH",
        description="Kantonskürzel oder 'CH' für die ganze Schweiz (z.B. 'GR', 'ZH')",
        max_length=2,
        pattern=r"^[A-Za-z]{2}$",  # Whitelist (SEC-018)
        strict=True,
    )
    data_type: str = Field(
        default="abschuss",
        description="Datentyp: 'abschuss', 'bestand', 'aussetzung', 'fallwild'",
        max_length=12,
        pattern=r"^[a-z]{5,12}$",  # Whitelist (SEC-018)
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("canton")
    @classmethod
    def _upper_canton(cls, v: str) -> str:
        return v.upper()

    @field_validator("data_type")
    @classmethod
    def _lower_dt(cls, v: str) -> str:
        return v.lower()


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
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class BafuDatasetDetailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    dataset_id: str = Field(
        ...,
        description="Dataset-ID oder Slug von opendata.swiss (z.B. 'nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen')",
        min_length=3,
        max_length=200,
        pattern=r"^[A-Za-z0-9_-]{3,200}$",  # Whitelist: Slug-Zeichen (SEC-018)
        strict=True,
    )


# --- Hilfsfunktionen ----------------------------------------------------------


def _format_flood_level(level: int) -> str:
    info = FLOOD_DANGER_LEVELS.get(
        level, {"label": "Unbekannt", "color": "grau", "description": ""}
    )
    return f"Stufe {level} ({info['label']}, {info['color']})"


# LINDAS-Dimension → (Anzeigename, Einheit) für die aktuelle Messwert-Tabelle.
_LINDAS_HYDRO_PARAMS: list[tuple[str, str, str]] = [
    ("discharge", "Abfluss", "m³/s"),
    ("level", "Pegel", "m ü.M."),
    ("temperature", "Wassertemperatur", "°C"),
]


def _format_hydro_current_lindas(d: dict[str, Any], response_format: ResponseFormat) -> str:
    """Formatiert einen aktuellen LINDAS-Messwert (SPARQL) als Markdown/JSON.

    Provenance ist `live_api` (LINDAS liefert typisierte Werte, im Gegensatz zum
    REST-Fallback-Pfad von hydrodaten.admin.ch).
    """
    rows: list[dict[str, Any]] = []
    for key, label, unit in _LINDAS_HYDRO_PARAMS:
        if d.get(key) is not None:
            rows.append({"parameter": label, "wert": d[key], "einheit": unit})
    danger = d.get("danger_level")

    if response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "source": "BAFU Hydrodaten via LINDAS (Open-Use / OGD-CH)",
                "provenance": "live_api",
                "station_id": d.get("station_id"),
                "name": d.get("name"),
                "gewaesser": d.get("water"),
                "zeitstempel": d.get("time"),
                "messwerte": rows,
                "gefahrenstufe": danger,
            },
            ensure_ascii=False,
            indent=2,
        )

    lines = [
        f"## Hydrologische Daten: {d.get('name', '–')} (Station {d.get('station_id')})\n",
        f"- **Gewässer:** {d.get('water') or '–'}",
        f"- **Zeitstempel:** {d.get('time', '–')}",
        "- **Quelle:** BAFU via LINDAS (SPARQL, Live-Werte)",
        "",
        "### Aktuelle Messwerte",
        "| Parameter | Wert | Einheit |",
        "|-----------|------|---------|",
    ]
    for r in rows:
        lines.append(f"| {r['parameter']} | **{r['wert']}** | {r['einheit']} |")
    if not rows:
        lines.append("| – | keine Werte verfügbar | – |")
    if danger:
        lines.append("")
        lines.append(f"**Gefahrenstufe:** {_format_flood_level(int(float(danger)))}")

    lines += [
        "",
        f"**Detailansicht:** https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{d.get('station_id')}",
        "",
        "*Tipp: Für historische Daten → `env_hydro_history` aufrufen "
        "(LINDAS liefert nur aktuelle Werte, keine Zeitreihe).*",
    ]
    return "\n".join(lines)


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
        lines.append(
            f"**Schweizer LRV-Grenzwert:** {lrv['limit']} µg/m³ → {status} ({lrv['ratio']}×)"
        )

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
@trace_tool
async def env_nabel_stations(params: NabelStationsInput, ctx: Context | None = None) -> str:
    """
    Listet alle 16 NABEL-Messstationen des nationalen Luftmessnetzes (BAFU) auf.

    Das NABEL (Nationales Beobachtungsnetz für Luftfremdstoffe) misst seit 1991
    kontinuierlich an 16 Standorten in der Schweiz: NO₂, O₃, PM10, PM2.5,
    SO₂, CO, Russ und weitere Parameter.

    <use_case>Einstieg in Luftqualitätsdaten: Stationsübersicht, um danach mit
    `env_nabel_current` die Messwerte einer konkreten Station zu holen.</use_case>
    <important_notes>16 feste NABEL-Stationen (statisch, kein Live-Call).</important_notes>

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
        return _envelope_json(
            source="BAFU – Nationales Beobachtungsnetz für Luftfremdstoffe (NABEL)",
            provenance="https://opendata.swiss/de/dataset/nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen",
            results=stations_list,
            match_type="exact",
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
@trace_tool
async def env_nabel_current(params: NabelCurrentInput, ctx: Context | None = None) -> str:
    """
    Ruft aktuelle und historische Luftqualitätsdaten einer NABEL-Station ab.

    Liefert Metadaten, Download-Links für Messdaten (CSV) sowie direkte
    Abfrage-URLs für den BAFU-Datenbrowser. Gemessene Parameter: NO₂, O₃,
    PM10, PM2.5, SO₂, CO, Russ (BC).

    <use_case>Aktuelle Luftqualität / Datenzugang einer konkreten NABEL-Station.</use_case>
    <important_notes>Liefert Metadaten + Datenlinks, keine Echtzeit-Rohwerte.
    Stationskürzel via `env_nabel_stations` ermitteln.</important_notes>

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
        await _handle_tool_error("env_nabel_current", e, ctx, station=code)

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
@trace_tool
async def env_air_limits_check(params: AirLimitsCheckInput, ctx: Context | None = None) -> str:
    """
    Bewertet einen gemessenen Luftschadstoffwert gegen Schweizer LRV-Grenzwerte
    und WHO 2021-Richtwerte.

    Unterstützte Schadstoffe: NO2, PM10, PM2.5, O3, SO2, CO.
    Grenzwerte gemäss Schweizer Luftreinhalte-Verordnung (LRV, SR 814.318.142.1).

    <use_case>Einen gemessenen Schadstoffwert gegen Schweizer LRV + WHO 2021
    einordnen (Überschreitung ja/nein, Verhältnis zum Grenzwert).</use_case>
    <important_notes>Rein lokale Berechnung (kein Netzwerk). Unterstützt
    NO2, PM10, PM2.5, O3, SO2, CO.</important_notes>

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
@trace_tool
async def env_hydro_stations(params: HydroStationsInput, ctx: Context | None = None) -> str:
    """
    Listet hydrologische Messstationen des BAFU an Schweizer Flüssen und Seen auf.

    Das BAFU betreibt ca. 260 Messstationen in der Schweiz. Stationen messen
    Wasserstand (Pegel), Abfluss (m³/s), Wassertemperatur und weitere Parameter
    in einem 10-Minuten-Intervall.

    <use_case>Hydromessstationen finden (nach Kanton/Gewässer), um danach mit
    `env_hydro_current` Pegel/Abfluss abzurufen.</use_case>
    <important_notes>Bei API-Ausfall Fallback mit Beispielstationen.
    Leeres Filterresultat → match_type "none".</important_notes>

    Args:
        params (HydroStationsInput):
            - canton: Kantonskürzel zum Filtern (z.B. 'ZH')
            - water_body: Gewässername zum Filtern (z.B. 'Limmat')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Stationsliste oder Fehlertext bei API-Problemen.
    """
    # Primärpfad: LINDAS SPARQL — volle Stationsabdeckung (233) + zuverlässige
    # Gewässernamen. LINDAS führt keinen Kanton-Code; bei gesetztem Kanton-Filter
    # wird direkt der REST-Pfad (unten) genutzt, der den Kanton mitliefert.
    if not params.canton:
        try:
            ls = await api.fetch_hydro_stations_lindas()
            filtered = [
                s
                for s in ls
                if not params.water_body or params.water_body.lower() in s["water"].lower()
            ]
            if params.response_format == ResponseFormat.JSON:
                return _envelope_json(
                    source="BAFU Hydrodaten via LINDAS",
                    provenance="live_api",
                    results=filtered[:100],
                    match_type="none" if not filtered else "exact",
                    note=(
                        f"Keine Stationen für Gewässer='{params.water_body}'. "
                        "Filter weglassen für die vollständige Liste."
                        if not filtered
                        else None
                    ),
                    query={"canton": params.canton, "water_body": params.water_body},
                )
            lines = [
                f"## Hydrologische Messstationen ({len(filtered)} Resultate)\n",
                f"*Filter: Gewässer={params.water_body or 'alle'} | Quelle: BAFU via LINDAS*\n",
                "| Station-ID | Name | Gewässer |",
                "|------------|------|---------|",
            ]
            for s in filtered[:50]:
                lines.append(f"| {s['id']} | {s['name']} | {s['water'] or '–'} |")
            if len(filtered) > 50:
                lines.append(f"\n*…und {len(filtered) - 50} weitere Stationen.*")
            if not filtered:
                lines.append(
                    "\n*Keine Treffer für diesen Filter (match_type: none). "
                    "Filter weglassen für die vollständige Liste, oder `env_hydro_current` "
                    "mit einer bekannten Station-ID (z.B. '2099' Limmat/Zürich) aufrufen.*"
                )
            lines.append("\n**Datenportal:** https://www.hydrodaten.admin.ch")
            return "\n".join(lines)
        except Exception as e:
            # LINDAS nicht erreichbar → auf REST-Pfad zurückfallen.
            await _handle_tool_error("env_hydro_stations", e, ctx, water_body=params.water_body)

    try:
        data = await api.fetch_hydro_stations()
    except Exception as e:
        error_msg = await _handle_tool_error("env_hydro_stations", e, ctx, canton=params.canton)
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
            if (not params.canton or params.canton.upper() == s["canton"]) and (
                not params.water_body or params.water_body.lower() in s["water"].lower()
            ):
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
        note = None
        if not filtered:
            note = (
                f"Keine Stationen für Filter (Kanton={params.canton or '–'}, "
                f"Gewässer={params.water_body or '–'}). Filter weglassen für die "
                f"vollständige Liste, oder `env_hydro_current` mit einer bekannten "
                f"Station-ID (z.B. '2099') aufrufen."
            )
        return _envelope_json(
            source="BAFU Hydrodaten",
            provenance="https://www.hydrodaten.admin.ch",
            results=filtered[:100],
            match_type="none" if not filtered else "exact",
            note=note,
            query={"canton": params.canton, "water_body": params.water_body},
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
    if not filtered:
        # ARCH-003: leeres Resultat mit actionable Hinweis statt blanker Tabelle
        lines.append(
            "\n*Keine Treffer für diesen Filter (match_type: none). "
            "Filter weglassen für die vollständige Liste, oder `env_hydro_current` "
            "mit einer bekannten Station-ID (z.B. '2099' Limmat/Zürich) aufrufen.*"
        )
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
@trace_tool
async def env_hydro_current(params: HydroCurrentInput, ctx: Context | None = None) -> str:
    """
    Ruft aktuelle Messwerte einer hydrologischen BAFU-Messstation ab.

    Liefert Pegel (m ü.M.), Abfluss (m³/s), Wassertemperatur (°C) sowie
    24h-Min/Max-Werte. Daten werden alle 10 Minuten aktualisiert.

    Bekannte Zürich-relevante Stationen:
      - 2099: Limmat – Zürich/Unterwerk
      - 2243: Sihl – Zürich
      - 2034: Zürichsee – Zürich/Tiefenbrunnen (Pegel)

    <use_case>Aktueller Pegel/Abfluss/Temperatur einer Station, z.B. für einen
    Hochwasser-Lagecheck.</use_case>
    <important_notes>Station-ID via `env_hydro_stations`. 10-Minuten-Aktualisierung.</important_notes>

    Args:
        params (HydroCurrentInput):
            - station_id: BAFU-Stationsnummer (z.B. '2099')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Aktuelle Messwerte inkl. Zeitstempel, oder Fallback mit direktem Link.
    """
    # Primärpfad: LINDAS SPARQL (typisierte Live-Werte: Abfluss/Pegel/Temperatur/
    # Gefahrenstufe). Bei Ausfall oder unbekannter Station → REST-Fallback.
    try:
        lindas = await api.fetch_hydro_current_lindas(params.station_id)
        if lindas.get("found"):
            return _format_hydro_current_lindas(lindas, params.response_format)
    except Exception as e:
        await _handle_tool_error("env_hydro_current", e, ctx, station_id=params.station_id)

    try:
        data = await api.fetch_hydro_station_data(params.station_id)
    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_hydro_current", e, ctx, station_id=params.station_id
        )
        portal_url = f"https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{params.station_id}"
        raise _terminal_failure(
            f"⚠️ Aktuelle Daten für Station {params.station_id} nicht abrufbar: {error_msg}\n\n"
            f"**Direktzugang:** {portal_url}\n"
            f"**Vollständiges Datenportal:** https://www.hydrodaten.admin.ch/de"
        )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {"station_id": params.station_id, "daten": data, "quelle": "BAFU Hydrodaten"},
            ensure_ascii=False,
            indent=2,
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
@trace_tool
async def env_hydro_history(params: HydroHistoryInput, ctx: Context | None = None) -> str:
    """
    Ruft historische Stundenwerte einer BAFU-Hydromesstations ab.

    Ermöglicht zeitliche Analysen von Wasserstand, Abfluss und Temperatur
    über bis zu 30 Tage. Ideal für Trendanalysen und Extremereignis-Recherche.

    <use_case>Aktuellsten Messwert einer Station holen und den Zugang zu echten
    historischen Zeitreihen (Tages-/Langzeitmittel) aufzeigen.</use_case>
    <important_notes>LINDAS liefert nur den aktuellen Wert (keine Zeitreihe).
    Historische Tages-/Langzeitmittel sind NICHT frei per API verfügbar und
    müssen bei der BAFU-Abfragezentrale bezogen werden.</important_notes>

    Args:
        params (HydroHistoryInput):
            - station_id: BAFU-Stationsnummer
            - parameter: 'Abfluss', 'Pegel' oder 'Temperatur' (Kontext)
            - days: Anzahl Tage (Kontext)

    Returns:
        str: Aktuellster Messwert (LINDAS) + Bezugsweg für historische Reihen.
    """
    # BUG-01: Der frühere CSV-Endpoint (hydrodaten.admin.ch/.../Hydrological_Data.csv)
    # ist stillgelegt (404). LINDAS liefert nur den aktuellen Wert; echte
    # historische Zeitreihen sind order-basiert (BAFU-Abfragezentrale).
    latest = None
    try:
        latest = await api.fetch_hydro_current_lindas(params.station_id)
    except Exception as e:
        await _handle_tool_error("env_hydro_history", e, ctx, station_id=params.station_id)

    portal_url = f"https://www.hydrodaten.admin.ch/de/seen-und-fluesse/{params.station_id}"
    lines = [
        f"## Hydrodaten Station {params.station_id} – Historie & Zugang\n",
        f"- **Angefragter Parameter:** {params.parameter}",
        "",
    ]

    if latest and latest.get("found"):
        lines += [
            f"### Aktuellster Messwert ({latest.get('name', '–')}, {latest.get('water') or '–'})",
            f"- **Stand:** {latest.get('time', '–')}",
            f"- **Abfluss:** {latest.get('discharge') or '–'} m³/s",
            f"- **Pegel:** {latest.get('level') or '–'} m ü.M.",
            f"- **Wassertemperatur:** {latest.get('temperature') or '–'} °C",
            "",
        ]

    lines += [
        "### Historische Zeitreihen (Tages-/Langzeitmittel)",
        "> **Nicht frei per API verfügbar.** LINDAS (`env_hydro_current`) liefert nur "
        "den *aktuellen* Wert. Historische Tagesmittel und langjährige Mittelwerte "
        "(z.B. für einen Vergleich «Sommer 2024 vs. langjähriges Mittel») müssen bei "
        "der **BAFU Hydrologischen Abfragezentrale** bezogen werden:",
        "- **E-Mail:** abfragezentrale@bafu.admin.ch",
        f"- **Interaktives Portal (Kurzverlauf/Grafik):** {portal_url}",
        "- **Datenkatalog:** https://opendata.swiss/de/organization/bafu",
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
@trace_tool
async def env_flood_warnings(params: FloodWarningsInput, ctx: Context | None = None) -> str:
    """
    Ruft aktuelle Hochwasserwarnungen aller BAFU-Messstationen in der Schweiz ab.

    Das BAFU gibt Hochwasserwarnungen in 5 Gefahrenstufen aus:
    1=Keine, 2=Mässig, 3=Erheblich, 4=Gross, 5=Sehr gross.

    <use_case>Aktive Hochwasserwarnungen schweizweit oder kantonal für eine
    Lagebeurteilung.</use_case>
    <important_notes>5 Gefahrenstufen. "Keine Warnung" ist eine explizite
    Entwarnung, kein Fehler.</important_notes>

    Args:
        params (FloodWarningsInput):
            - min_level: Minimale Gefahrenstufe (Standard: 2)
            - canton: Kantonskürzel zum Filtern

    Returns:
        str: Aktuell aktive Hochwasserwarnungen, gefiltert nach Gefahrenstufe.
    """
    # Datenquelle: LINDAS `dangerLevel` (der frühere REST-Endpoint
    # hydrodaten.admin.ch/.../warnings.json ist stillgelegt / 404).
    # LINDAS führt keinen Kanton-Code → der canton-Filter ist hier nicht wirksam.
    canton_note = (
        f" (Hinweis: Kantonsfilter '{params.canton}' via LINDAS nicht verfügbar — "
        "es werden alle Stationen gezeigt)"
        if params.canton
        else ""
    )
    try:
        warnings = await api.fetch_hydro_warnings_lindas(params.min_level)
    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_flood_warnings", e, ctx, min_level=params.min_level
        )
        raise _terminal_failure(
            f"⚠️ Warnungsdaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang zu aktuellen Warnungen:**\n"
            "- https://www.hydrodaten.admin.ch/de/hochwasserwarnungen\n"
            "- https://www.naturgefahren.ch (Übersichtsseite Naturgefahren)"
        )

    if params.response_format == ResponseFormat.JSON:
        return _envelope_json(
            source="BAFU Hydrodaten via LINDAS – Gefahrenstufen",
            provenance="live_api",
            results=warnings,
            match_type="none" if not warnings else "exact",
            note=(
                f"Keine aktiven Warnungen (Stufe ≥ {params.min_level})."
                if not warnings
                else (canton_note.strip() or None)
            ),
            query={"min_level": params.min_level, "canton": params.canton},
        )

    if not warnings:
        return (
            f"✅ **Keine aktiven Hochwasserwarnungen** (Stufe ≥ {params.min_level}).\n\n"
            f"*Quelle: BAFU via LINDAS.*{canton_note}\n\n"
            "**Aktuelle Übersicht:** https://www.hydrodaten.admin.ch/de/hochwasserwarnungen"
        )

    lines = [
        f"## ⚠️ Aktive Hochwasserwarnungen ({len(warnings)} Stationen)\n",
        f"*Filter: Stufe ≥ {params.min_level} | Quelle: BAFU via LINDAS*{canton_note}\n",
        "| Station | Gewässer | Gefahrenstufe |",
        "|---------|---------|---------------|",
    ]
    for w in warnings:
        lines.append(
            f"| {w['name']} | {w['water'] or '–'} | {_format_flood_level(w['danger_level'])} |"
        )
    lines += [
        "",
        "**Gefahrenstufen:** 1=Keine | 2=Mässig | 3=Erheblich | 4=Gross | 5=Sehr gross",
        "**Quelle:** https://www.hydrodaten.admin.ch/de/hochwasserwarnungen",
    ]
    return "\n".join(lines)


# --- Badegewässerqualität (LINDAS-Cube ubd01041prod, Nachtrag N1/N6) ----------

# Basis-URI der aktuellen Cube-Serie; die konkrete Version (z.B. .../13) wird
# zur Laufzeit über die Versions-Deduplizierung der Cube-Schicht ermittelt.
_BATHING_CUBE_BASE = "https://environment.ld.admin.ch/foen/ubd01041prod"
_BATHING_DIM = f"{_BATHING_CUBE_BASE}/"
_BATHING_DIM_LOCATION = f"{_BATHING_DIM}location"
_BATHING_DIM_DATE = f"{_BATHING_DIM}dateofprobing"

# BFS-Kantonsnummer → Kürzel (Badestellen tragen `containedInPlace` als
# ld.admin.ch/canton/NN — die Nummer ist der Join-Key, N4).
CANTON_NUMBER_TO_ABBR: dict[int, str] = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL",
    9: "ZG", 10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR",
    16: "AI", 17: "SG", 18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD",
    23: "VS", 24: "NE", 25: "GE", 26: "JU",
}  # fmt: skip


async def _bathing_cube_uri() -> str | None:
    """Ermittelt die aktuelle Version des Badegewässer-Cubes (Versions-Dedup)."""
    cubes = await lindas_cube.find_cubes(api.run_sparql, "badegewässer")
    for c in cubes:
        if lindas_cube.base_cube_uri(c.get("cube", "")) == _BATHING_CUBE_BASE:
            return c["cube"]
    return cubes[0]["cube"] if cubes else None


@mcp.tool(
    name="env_bathing_water",
    annotations={
        "title": "Badegewässerqualität (E.coli/Enterokokken)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@trace_tool
async def env_bathing_water(params: BathingWaterInput, ctx: Context | None = None) -> str:
    """
    Ruft die Badegewässerqualität der BAFU-Erhebung ab (LINDAS-Data-Cube).

    Die Erhebung misst die hygienische Qualität von Badestellen an Schweizer
    Seen und Flüssen über E.coli- und Enterokokken-Konzentrationen. Im
    Gegensatz zu Pegel/Abfluss ist dies eine echte Mehrjahres-Zeitreihe
    (Saisondaten seit 2020, jährliche Nachführung).

    <use_case>Wasserqualität einer Badestelle prüfen («Kann man bei X baden?»)
    oder Badestellen eines Kantons auflisten.</use_case>
    <important_notes>Ohne `location` wird eine Badestellen-Übersicht geliefert;
    mit `location` die letzten Probenwerte dieser Stelle. Daten werden jährlich
    nach der Badesaison nachgeführt (kein Echtzeit-Monitoring).</important_notes>

    Args:
        params (BathingWaterInput):
            - location: Badestellen-Name (Teilstring), leer = Übersicht
            - canton: Kantonskürzel zum Filtern
            - limit: max. Anzahl Messwerte bzw. Badestellen
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Probenwerte mit aufgelösten Standort-Labels, Kantonsnummer
             (Join-Key) und Lizenzfeld — nie rohe Code-URIs.
    """
    canton = params.canton.upper()
    try:
        cube_uri = await _bathing_cube_uri()
        if cube_uri is None:
            return (
                "⚠️ Badegewässer-Cube in LINDAS nicht gefunden (Datenbestand "
                "möglicherweise im Umbau). Direktzugang: https://www.bafu.admin.ch "
                "→ Thema Wasser → Badegewässerqualität."
            )
        # Lizenz- und Standort-Query hängen beide nur am cube_uri und sind
        # voneinander unabhängig → parallel ausführen (Audit ARCH-007).
        license_info, sites = await asyncio.gather(
            lindas_cube.get_cube_license(api.run_sparql, cube_uri),
            lindas_cube.find_dimension_values(
                api.run_sparql,
                cube_uri,
                _BATHING_DIM_LOCATION,
                name_contains=params.location,
                limit=200,
            ),
        )
        if canton:
            wanted = {n for n, a in CANTON_NUMBER_TO_ABBR.items() if a == canton}
            sites = [s for s in sites if s.get("canton_number") in wanted]

        # Ohne Location-Filter: Übersicht der Badestellen (keine Messwerte).
        if not params.location:
            rows = [
                {
                    "badestelle": s.get("name", "–"),
                    "code": s.get("identifier", ""),
                    "kanton": CANTON_NUMBER_TO_ABBR.get(s.get("canton_number", 0), "–"),
                    "kanton_nummer": s.get("canton_number"),
                }
                for s in sites[: params.limit]
            ]
            if params.response_format == ResponseFormat.JSON:
                return _envelope_json(
                    source=f"BAFU Badegewässerqualität via LINDAS — {license_info}",
                    provenance="live_api",
                    results=rows,
                    match_type="none" if not rows else "exact",
                    note=f"{len(sites)} Badestellen insgesamt; `location` setzen für Messwerte.",
                    query={"canton": canton},
                )
            lines = [
                f"## Badestellen der BAFU-Erhebung ({len(sites)} Treffer)\n",
                f"*Filter: Kanton={canton or 'alle'} | Quelle: BAFU via LINDAS*\n",
                "| Badestelle | Code | Kanton |",
                "|------------|------|--------|",
            ]
            for r in rows:
                lines.append(f"| {r['badestelle']} | {r['code'] or '–'} | {r['kanton']} |")
            if len(sites) > params.limit:
                lines.append(f"\n*…und {len(sites) - params.limit} weitere Badestellen.*")
            if not rows:
                lines.append("\n*Keine Badestellen für diesen Filter (match_type: none).*")
            lines.append(f"\n*Messwerte einer Stelle: `location` setzen. {license_info}*")
            return "\n".join(lines)

        if not sites:
            return (
                f"Keine Badestelle für '{params.location}'"
                + (f" im Kanton {canton}" if canton else "")
                + " gefunden (match_type: none). Tipp: `env_bathing_water` ohne "
                "`location` listet alle Badestellen der Erhebung."
            )

        # Mit Location: letzte Probenwerte der besten Treffer-Badestelle.
        site = sites[0]
        observations = await lindas_cube.get_observations(
            api.run_sparql,
            cube_uri,
            filters={_BATHING_DIM_LOCATION: site["value"]},
            order_desc_by=_BATHING_DIM_DATE,
            limit=params.limit,
        )
        site_canton = CANTON_NUMBER_TO_ABBR.get(site.get("canton_number", 0), "–")
        results = [
            {
                "datum": o.get("dateofprobing", "–"),
                "parameter": o.get("parametertype", "–"),
                "konzentration": o.get("value", "–"),
                "einheit": "KBE/100 ml",
            }
            for o in observations
        ]
        alternates = [s.get("name", "") for s in sites[1:4]]

        if params.response_format == ResponseFormat.JSON:
            return _envelope_json(
                source=f"BAFU Badegewässerqualität via LINDAS — {license_info}",
                provenance="live_api",
                results=results,
                match_type="fuzzy" if len(sites) > 1 else "exact",
                note=(
                    f"Badestelle: {site.get('name')} (Code {site.get('identifier', '–')}, "
                    f"Kanton {site_canton}, Kantonsnummer {site.get('canton_number', '–')})."
                    + (f" Weitere Treffer: {', '.join(alternates)}." if alternates else "")
                ),
                query={"location": params.location, "canton": canton},
            )

        lines = [
            f"## Badegewässerqualität: {site.get('name', '–')} "
            f"(Code {site.get('identifier', '–')}, Kanton {site_canton})\n",
            "*Quelle: BAFU via LINDAS | Parameter: E.coli & Enterokokken (KBE/100 ml)*\n",
            "| Datum | Parameter | Konzentration |",
            "|-------|-----------|---------------|",
        ]
        for r in results:
            lines.append(f"| {r['datum']} | {r['parameter']} | **{r['konzentration']}** |")
        if not results:
            lines.append("| – | keine Probenwerte verfügbar | – |")
        if alternates:
            lines.append(f"\n*Weitere Treffer für '{params.location}': {', '.join(alternates)}*")
        lines += [
            "",
            "*Daten werden jährlich nach der Badesaison nachgeführt (kein Echtzeit-Monitoring).*",
            f"*{license_info}*",
        ]
        return "\n".join(lines)
    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_bathing_water", e, ctx, location=params.location, canton=canton
        )
        raise _terminal_failure(
            f"⚠️ Badegewässerdaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:** https://www.bafu.admin.ch (Thema Wasser → "
            "Badegewässerqualität) bzw. https://opendata.swiss/de/organization/bafu"
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
@trace_tool
async def env_hazard_overview(params: HazardOverviewInput, ctx: Context | None = None) -> str:
    """
    Ruft das aktuelle Naturgefahren-Bulletin für die Schweiz ab.

    Das Bulletin wird täglich vom Institut für Schnee- und Lawinenforschung (SLF)
    und BAFU herausgegeben und umfasst: Hochwasser, Lawinen, Steinschlag,
    Rutschungen und Sturm.

    <use_case>Tagesaktuelles Naturgefahren-Bulletin (Lawinen, Hochwasser,
    Sturm, Rutschungen) für die ganze Schweiz.</use_case>
    <important_notes>Quelle SLF/BAFU, mehrsprachig (de/fr/it/en).</important_notes>

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
        error_msg = await _handle_tool_error(
            "env_hazard_overview", e, ctx, language=params.language
        )
        raise _terminal_failure(
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
@trace_tool
async def env_hazard_regions(params: HazardRegionsInput, ctx: Context | None = None) -> str:
    """
    Ruft regionsspezifische Naturgefahrenwarnungen ab.

    Ermöglicht gezielte Abfragen für Schulausflüge, Events oder
    Infrastrukturplanung in einem spezifischen Gebiet der Schweiz.

    <use_case>Regionsspezifische Gefahren für Events, Schulausflüge oder
    Infrastrukturplanung.</use_case>
    <important_notes>Region + optional Gefahrentyp filtern; bei leerem Resultat
    werden Karten-Links geliefert.</important_notes>

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
        error_msg = await _handle_tool_error("env_hazard_regions", e, ctx, region=params.region)
        raise _terminal_failure(
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
@trace_tool
async def env_wildfire_danger(params: WildfireDangerInput, ctx: Context | None = None) -> str:
    """
    Ruft den aktuellen Waldbrandgefahren-Index nach Regionen ab.

    Die Waldbrandgefahr wird täglich durch das BAFU berechnet und auf
    einer 5-stufigen Skala (gering bis sehr gross) kommuniziert.
    Relevant für Schulausflüge, Events und Forstbetriebe.

    <use_case>Waldbrandgefahr-Index pro Region/Kanton, z.B. für Forstbetriebe
    oder Event-Planung.</use_case>
    <important_notes>5-stufige Skala, tagesaktuell (de/fr/it).</important_notes>

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
                icon = (
                    "🟢" if level <= 1 else ("🟡" if level == 2 else ("🟠" if level == 3 else "🔴"))
                )
                lines.append(
                    f"| {name} | {canton} | {icon} Stufe {level} | {level_info['label']} |"
                )
        else:
            lines.append("*Keine Regionaldaten verfügbar.*")

        lines += [
            "",
            "**Aktuelle Gefahrenkarte:** https://www.waldbrandgefahr.ch/de/aktuelle-lage",
            "**Verhaltensregeln bei Waldbrandgefahr:** https://www.bafu.admin.ch/de/themen/wald/waldbrand",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_wildfire_danger", e, ctx, language=params.language
        )
        raise _terminal_failure(
            f"⚠️ Waldbranddaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:**\n"
            "- https://www.waldbrandgefahr.ch/de/aktuelle-lage\n"
            "- https://www.naturgefahren.ch\n"
        )


# --- TOOLS: SCHNEE & LAWINEN / SLF --------------------------------------------

_SLF_ATTRIBUTION = "SLF (WSL-Institut für Schnee- und Lawinenforschung) – CC BY 4.0"


def _avalanche_level_from(value: Any) -> int | None:
    """Normalisiert einen CAAML-Gefahrenwert (Zahl 1–5 oder EAWS-Textwert)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        level = int(value)
        return level if 1 <= level <= 5 else None
    text = str(value).strip().lower()
    if text.isdigit():
        level = int(text)
        return level if 1 <= level <= 5 else None
    return _AVALANCHE_WORD_TO_LEVEL.get(text)


def _extract_avalanche_danger(props: dict[str, Any]) -> int | None:
    """Best-effort-Extraktion der Gefahrenstufe aus einem CAAML-Feature.

    CAAML/EAWS-Schemata variieren; defensiv mehrere Formen prüfen statt anzunehmen.
    """
    ratings = props.get("dangerRatings") or props.get("danger_ratings")
    if isinstance(ratings, list) and ratings and isinstance(ratings[0], dict):
        r0 = ratings[0]
        level = _avalanche_level_from(
            r0.get("mainValue") or r0.get("main_value") or r0.get("value")
        )
        if level is not None:
            return level
    for key in ("maxDangerLevel", "dangerLevel", "danger_level", "maxdanger"):
        level = _avalanche_level_from(props.get(key))
        if level is not None:
            return level
    return None


@mcp.tool(
    name="env_snow_stations",
    annotations={
        "title": "SLF-Schneemessstationen (IMIS) auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@trace_tool
async def env_snow_stations(params: SnowStationsInput, ctx: Context | None = None) -> str:
    """
    Listet die automatischen IMIS-Schneemessstationen des SLF auf.

    Das SLF betreibt ein Netz automatischer Stationen (IMIS) in den Schweizer
    Bergen, die u.a. Schneehöhe, Neuschnee, Wind und Temperaturen messen.

    <use_case>Einstieg in die Schneedaten: Stationsübersicht (nach Kanton), um
    danach mit `env_snow_current` Schneehöhe/Neuschnee abzurufen.</use_case>
    <important_notes>Datenquelle SLF (CC BY 4.0). `type`=SNOW_FLAT sind
    Flachfeld-Schneestationen. Kein Niederschlags-Tool (→ meteoswiss-mcp).</important_notes>

    Args:
        params (SnowStationsInput):
            - canton: Kantonskürzel zum Filtern (z.B. 'GR')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Stationsliste mit Code, Name, Kanton, Höhe und Typ.
    """
    try:
        stations = await api.fetch_slf_snow_stations()
    except Exception as e:
        error_msg = await _handle_tool_error("env_snow_stations", e, ctx, canton=params.canton)
        raise _terminal_failure(
            f"⚠️ SLF-Stationsliste nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/messwerte-und-messstationen/\n"
        )

    canton = params.canton.upper()
    filtered = [
        s for s in stations if not canton or str(s.get("canton_code", "")).upper() == canton
    ]

    if params.response_format == ResponseFormat.JSON:
        return _envelope_json(
            source=_SLF_ATTRIBUTION,
            provenance="live_api",
            results=filtered[:200],
            match_type="none" if not filtered else "exact",
            note=(f"Keine IMIS-Stationen im Kanton {canton}." if not filtered else None),
            query={"canton": params.canton},
        )

    lines = [
        f"## SLF-Schneemessstationen (IMIS) – {len(filtered)} Stationen\n",
        f"*Filter: Kanton={params.canton or 'alle'} | Quelle: {_SLF_ATTRIBUTION}*\n",
        "| Code | Name | Kanton | Höhe (m) | Typ |",
        "|------|------|--------|----------|-----|",
    ]
    for s in sorted(filtered, key=lambda x: str(x.get("canton_code", "")))[:60]:
        lines.append(
            f"| {s.get('code', '–')} | {s.get('label', '–')} | {s.get('canton_code', '–')} "
            f"| {int(s['elevation']) if s.get('elevation') is not None else '–'} "
            f"| {s.get('type', '–')} |"
        )
    if len(filtered) > 60:
        lines.append(f"\n*…und {len(filtered) - 60} weitere Stationen.*")
    if not filtered:
        lines.append(
            f"\n*Keine Stationen im Kanton {canton} (match_type: none). "
            "Filter weglassen für alle Stationen.*"
        )
    lines.append("\n*Tipp: Aktuelle Schneehöhe/Neuschnee → `env_snow_current` aufrufen.*")
    return "\n".join(lines)


@mcp.tool(
    name="env_snow_current",
    annotations={
        "title": "Aktuelle Schneehöhe & Neuschnee (SLF)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@trace_tool
async def env_snow_current(params: SnowCurrentInput, ctx: Context | None = None) -> str:
    """
    Ruft aktuelle Schneehöhe (HS) und Neuschnee 24 h (HN_1D) der SLF-IMIS-
    Stationen ab.

    Werte in cm, modelliert aus dem SLF-Schneedeckenmodell. Ausserhalb der
    Schneesaison sind die Werte 0 (schneefrei) – das ist kein Fehler.

    <use_case>Aktuelle Schneelage nach Kanton oder Station, z.B. für
    Tourenplanung oder Schulausflüge.</use_case>
    <important_notes>HS/HN_1D in cm. Kein Niederschlag (→ meteoswiss-mcp).
    Datenquelle SLF (CC BY 4.0).</important_notes>

    Args:
        params (SnowCurrentInput):
            - canton: Kantonskürzel zum Filtern
            - station: IMIS-Stationscode zum Filtern
            - limit: max. Anzahl Stationen
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Schneehöhe und Neuschnee je Station, nach Schneehöhe absteigend.
    """
    try:
        # Tages-Schneewerte und Stations-Metadaten sind zwei unabhängige
        # SLF-Endpoints → parallel abrufen (Audit ARCH-007).
        snow, stations = await asyncio.gather(
            api.fetch_slf_daily_snow(),
            api.fetch_slf_snow_stations(),
        )
    except Exception as e:
        error_msg = await _handle_tool_error("env_snow_current", e, ctx, canton=params.canton)
        raise _terminal_failure(
            f"⚠️ SLF-Schneedaten nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/\n"
        )

    meta = {s.get("code"): s for s in stations}
    canton = params.canton.upper()
    station = params.station.upper()

    rows: list[dict[str, Any]] = []
    for rec in snow:
        code = rec.get("station_code")
        info = meta.get(code, {})
        if station and str(code).upper() != station:
            continue
        if canton and str(info.get("canton_code", "")).upper() != canton:
            continue
        rows.append(
            {
                "code": code,
                "name": info.get("label", ""),
                "canton": info.get("canton_code", ""),
                "hs_cm": rec.get("HS"),
                "hn_1d_cm": rec.get("HN_1D"),
                "date": rec.get("measure_date"),
            }
        )

    rows.sort(key=lambda r: r["hs_cm"] if r["hs_cm"] is not None else -1, reverse=True)
    shown = rows[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return _envelope_json(
            source=_SLF_ATTRIBUTION,
            provenance="live_api",
            results=shown,
            match_type="none" if not rows else "exact",
            note=(
                "Keine Stationen für diesen Filter."
                if not rows
                else (
                    "Alle Werte 0 cm – aktuell schneefrei."
                    if all((r["hs_cm"] or 0) == 0 for r in rows)
                    else None
                )
            ),
            query={"canton": params.canton, "station": params.station},
        )

    if not rows:
        return (
            f"## SLF-Schneedaten\n\n*Keine Stationen für Filter "
            f"(Kanton={params.canton or '–'}, Station={params.station or '–'}) "
            "(match_type: none). Filter weglassen oder Stationscode via "
            "`env_snow_stations` prüfen.*"
        )

    max_hs = max((r["hs_cm"] or 0) for r in rows)
    lines = [
        f"## Aktuelle Schneelage (SLF/IMIS) – {len(rows)} Stationen\n",
        f"*Filter: Kanton={params.canton or 'alle'}, Station={params.station or 'alle'} "
        f"| Quelle: {_SLF_ATTRIBUTION}*\n",
        "| Code | Name | Kanton | Schneehöhe HS (cm) | Neuschnee 24h (cm) |",
        "|------|------|--------|--------------------|--------------------|",
    ]
    for r in shown:
        lines.append(
            f"| {r['code']} | {r['name'] or '–'} | {r['canton'] or '–'} "
            f"| {r['hs_cm'] if r['hs_cm'] is not None else '–'} "
            f"| {r['hn_1d_cm'] if r['hn_1d_cm'] is not None else '–'} |"
        )
    if len(rows) > params.limit:
        lines.append(f"\n*…und {len(rows) - params.limit} weitere Stationen.*")
    if max_hs == 0:
        lines.append("\n*Alle gezeigten Stationen aktuell schneefrei (HS = 0 cm).*")
    return "\n".join(lines)


@mcp.tool(
    name="env_avalanche_bulletin",
    annotations={
        "title": "Lawinenbulletin / Warnstufen (SLF)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@trace_tool
async def env_avalanche_bulletin(params: AvalancheBulletinInput, ctx: Context | None = None) -> str:
    """
    Ruft das aktuelle Lawinenbulletin des SLF ab (Warnstufen je Region).

    Gefahrenstufen nach europäischer EAWS-Skala 1–5 (Gering bis Sehr gross).
    Ausserhalb der Lawinensaison wird kein Bulletin publiziert – dann meldet das
    Tool explizit «kein aktives Bulletin» (kein Fehler).

    <use_case>Aktuelle Lawinengefahr je Warnregion für Tourenplanung oder
    Sicherheitsbeurteilung.</use_case>
    <important_notes>EAWS-Skala 1–5. Saisonal (Winter). Datenquelle SLF
    (CC BY 4.0). Für Schneehöhen → `env_snow_current`.</important_notes>

    Args:
        params (AvalancheBulletinInput):
            - language: 'de', 'fr', 'it', 'en'
            - region: Regionsname/-code (Teilstring) zum Filtern

    Returns:
        str: Warnstufen je Region oder Hinweis, dass kein Bulletin aktiv ist.
    """
    try:
        data = await api.fetch_slf_avalanche_bulletin(params.language)
    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_avalanche_bulletin", e, ctx, language=params.language
        )
        raise _terminal_failure(
            f"⚠️ Lawinenbulletin nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/\n"
        )

    features = data.get("features", []) if isinstance(data, dict) else []
    if not features:
        return (
            "## 🏔️ Lawinenbulletin SLF\n\n"
            "**Aktuell kein aktives Lawinenbulletin.** Ausserhalb der Lawinensaison "
            "(i.d.R. ca. Mai–November) publiziert das SLF kein Bulletin.\n\n"
            "**Aktuelle Lage:** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/"
        )

    region_filter = params.region.lower()
    entries: list[dict[str, Any]] = []
    for feat in features:
        props = feat.get("properties", {}) if isinstance(feat, dict) else {}
        name = str(
            props.get("region") or props.get("name") or props.get("label") or props.get("id") or "–"
        )
        if region_filter and region_filter not in name.lower():
            continue
        entries.append({"region": name, "level": _extract_avalanche_danger(props)})

    lines = [
        "## 🏔️ Lawinenbulletin SLF\n",
        f"*Sprache: {params.language} | {len(entries)} Warnregionen "
        f"| Quelle: {_SLF_ATTRIBUTION}*\n",
        "**Gefahrenstufen (EAWS):** 1=Gering | 2=Mässig | 3=Erheblich | 4=Gross | 5=Sehr gross\n",
        "| Warnregion | Gefahrenstufe |",
        "|------------|---------------|",
    ]
    for e in entries[:60]:
        lvl = e["level"]
        if lvl is not None:
            info = AVALANCHE_DANGER_LEVELS.get(lvl, {"label": "–", "color": "–"})
            lines.append(f"| {e['region']} | Stufe {lvl} ({info['label']}, {info['color']}) |")
        else:
            lines.append(f"| {e['region']} | – (keine Angabe im Feature) |")
    if not entries:
        lines.append(f"| – | keine Region enthält '{params.region}' |")

    lines.append(
        "\n**Vollständiges Bulletin:** https://www.slf.ch/de/lawinenbulletin-und-schneesituation/"
    )
    return "\n".join(lines)


# --- TOOLS: JAGD & WILDTIERE / Eidg. Jagdstatistik ----------------------------

_JAGD_ATTRIBUTION = "BAFU – Eidg. Jagdstatistik (jagdstatistik.ch), Quellenangabe erforderlich"


@mcp.tool(
    name="env_hunting_species",
    annotations={
        "title": "Jagdbare Tierarten auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@trace_tool
async def env_hunting_species(params: HuntingSpeciesInput, ctx: Context | None = None) -> str:
    """
    Listet die in der Eidg. Jagdstatistik erfassten Tierarten mit ihren Codes auf.

    Die Liste ist statisch eingebettet (aus der Live-Probe) und dient als
    Nachschlagewerk für `env_hunting_stats` (Parameter `species`).

    <use_case>Verfügbare Tierarten + Codes nachschlagen, bevor mit
    `env_hunting_stats` Abschuss-/Fallwildzahlen abgefragt werden.</use_case>
    <important_notes>Rein lokal (kein Netzwerk). 36 Arten (Huftiere, Raubtiere,
    weitere Säuger).</important_notes>

    Args:
        params (HuntingSpeciesInput):
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Liste der Tierarten mit sp-Code und Name.
    """
    species = [{"code": c, "name": n} for c, n in sorted(JAGD_SPECIES.items(), key=lambda x: x[1])]

    if params.response_format == ResponseFormat.JSON:
        return _envelope_json(
            source=_JAGD_ATTRIBUTION,
            provenance="cached",
            results=species,
            match_type="exact",
        )

    lines = [
        f"## Jagdbare Tierarten (Eidg. Jagdstatistik) – {len(species)} Arten\n",
        f"*Quelle: {_JAGD_ATTRIBUTION}*\n",
        "| Name | Code | | Name | Code |",
        "|------|------|---|------|------|",
    ]
    half = (len(species) + 1) // 2
    left, right = species[:half], species[half:]
    for i in range(half):
        li = left[i]
        ri = right[i] if i < len(right) else {"name": "", "code": ""}
        lines.append(
            f"| {li['name']} | `{li['code']}` | | {ri['name']} | {('`' + ri['code'] + '`') if ri['code'] else ''} |"
        )
    lines.append("\n*Datentypen für `env_hunting_stats`: abschuss, bestand, aussetzung, fallwild.*")
    return "\n".join(lines)


@mcp.tool(
    name="env_hunting_stats",
    annotations={
        "title": "Jagdstatistik: Abschuss/Fallwild je Art & Kanton",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@trace_tool
async def env_hunting_stats(params: HuntingStatsInput, ctx: Context | None = None) -> str:
    """
    Ruft Zeitreihen der Eidg. Jagdstatistik ab: Abschuss-, Bestand-, Aussetzungs-
    oder Fallwildzahlen je Tierart und Kanton (Jahre 2015–2024).

    Datenherr ist das BAFU. Der zugrundeliegende Endpoint ist undokumentiert
    (Web-App-Backend); ein Schema-Guard fängt Strukturänderungen ab.

    <use_case>Entwicklung der Abschuss- oder Fallwildzahlen einer Tierart in
    einem Kanton über die Zeit.</use_case>
    <important_notes>Tierart via Name oder Code (siehe `env_hunting_species`).
    Werte je Alters-/Geschlechtsklasse; Total = Summe. Jagdjahr meist 1. Apr.–31. März.</important_notes>

    Args:
        params (HuntingStatsInput):
            - species: Tierart (Name oder sp-Code)
            - canton: Kantonskürzel oder 'CH'
            - data_type: 'abschuss', 'bestand', 'aussetzung', 'fallwild'
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Jahreswerte (Total + Klassen) oder aktionabler Hinweis bei Problemen.
    """
    sp_code = _resolve_species(params.species)
    if sp_code is None:
        return (
            f"Fehler: Tierart '{params.species}' nicht erkannt.\n"
            "Tipp: `env_hunting_species` für die vollständige Liste aufrufen."
        )
    if params.canton not in JAGD_CANTONS:
        known = ", ".join(sorted(JAGD_CANTONS))
        return f"Fehler: Kanton '{params.canton}' unbekannt. Erlaubt: {known}"
    th = JAGD_DATATYPES.get(params.data_type)
    if th is None:
        return (
            f"Fehler: Datentyp '{params.data_type}' unbekannt. "
            f"Erlaubt: {', '.join(JAGD_DATATYPES)}."
        )

    try:
        data = await api.fetch_jagd_statistics(sp_code, th, params.canton)
    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_hunting_stats", e, ctx, species=sp_code, canton=params.canton
        )
        raise _terminal_failure(
            f"⚠️ Jagdstatistik nicht abrufbar: {error_msg}\n\n"
            "**Direktzugang:** https://www.jagdstatistik.ch/de/home\n"
        )

    # Schema-Guard (Graceful Degradation): Struktur hat sich geändert.
    if not data.get("found"):
        return (
            "⚠️ Die Jagdstatistik-Auswertung konnte nicht ausgelesen werden "
            "(unerwartete Datenstruktur des Backends).\n\n"
            "**Direktzugang:** https://www.jagdstatistik.ch/de/home"
        )

    years = data["years"]
    series = data["series"]
    species_name = JAGD_SPECIES[sp_code]
    canton_name = JAGD_CANTONS[params.canton]

    # Total je Jahr über alle Klassen.
    totals: list[int | float] = []
    for i in range(len(years)):
        total: float = 0
        for s in series:
            vals = s["values"]
            v = vals[i] if i < len(vals) else 0
            if isinstance(v, (int, float)):
                total += v
        totals.append(int(total) if float(total).is_integer() else total)

    if params.response_format == ResponseFormat.JSON:
        results = [
            {
                "jahr": years[i],
                "total": totals[i],
                "klassen": {
                    s["name"]: (s["values"][i] if i < len(s["values"]) else None) for s in series
                },
            }
            for i in range(len(years))
        ]
        return _envelope_json(
            source=_JAGD_ATTRIBUTION,
            provenance="live_api",
            results=results,
            match_type="exact" if results else "none",
            query={
                "species": species_name,
                "canton": params.canton,
                "data_type": params.data_type,
            },
        )

    dt_label = params.data_type.capitalize()
    lines = [
        f"## Jagdstatistik: {species_name} – {dt_label} ({canton_name})\n",
        f"*Zeitraum: {years[0] if years else '–'}–{years[-1] if years else '–'} "
        f"| Quelle: {_JAGD_ATTRIBUTION}*\n",
    ]
    # Klassen als Spalten (max 6), plus Total.
    shown_classes = series[:6]
    header = "| Jahr | Total | " + " | ".join(s["name"] for s in shown_classes) + " |"
    sep = "|------|-------|" + "|".join(["------"] * len(shown_classes)) + "|"
    lines += [header, sep]
    for i, yr in enumerate(years):
        cells = " | ".join(
            str(s["values"][i]) if i < len(s["values"]) else "–" for s in shown_classes
        )
        lines.append(f"| {yr} | **{totals[i]}** | {cells} |")
    if len(series) > 6:
        lines.append(f"\n*…und {len(series) - 6} weitere Klassen (JSON-Modus für alle).*")
    lines.append("\n**Quelle/Details:** https://www.jagdstatistik.ch/de/home")
    return "\n".join(lines)


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
@trace_tool
async def env_bafu_datasets(params: BafuDatasetsInput, ctx: Context | None = None) -> str:
    """
    Sucht BAFU-Datensätze auf dem Schweizer Open-Data-Portal opendata.swiss.

    Das BAFU publiziert Datensätze zu Luft, Wasser, Boden, Biodiversität,
    Lärm, Klima, Wald und weiteren Umweltthemen als offene Daten (OGD).
    Ergebnisse enthalten Titel, Beschreibung und Download-URLs (CSV, JSON, WMS).

    <use_case>BAFU-Open-Data auf opendata.swiss durchsuchen (CSV/JSON/WMS), um
    danach mit `env_bafu_dataset_detail` Details/Download-URLs zu holen.</use_case>
    <important_notes>Paginierung via offset/rows. 0 Treffer → match_type "none",
    dann breitere Begriffe versuchen.</important_notes>

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

        if params.response_format == ResponseFormat.JSON:
            return _envelope_json(
                source="BAFU – opendata.swiss (CKAN)",
                provenance="https://opendata.swiss/de/organization/bafu",
                results=datasets,
                match_type="none" if not datasets else "exact",
                note=(
                    f"Keine Treffer für '{params.query}'. Breitere Begriffe versuchen."
                    if not datasets
                    else None
                ),
                query={"query": params.query, "rows": params.rows, "offset": params.offset},
            )

        # ARCH-003: leeres Resultat mit actionable Hinweis statt blanker Liste
        if not datasets:
            return (
                f"## BAFU-Datensätze auf opendata.swiss\n\n"
                f"**0 Treffer** für '{params.query or 'alle BAFU-Datensätze'}' "
                f"(match_type: none).\n\n"
                f"*Tipp: Breitere Begriffe nutzen (z.B. 'Luft', 'Wasser', 'Wald'), "
                f"die Schreibweise prüfen, oder ohne `query` alle BAFU-Datensätze listen.*\n\n"
                f"**Direktzugang:** https://opendata.swiss/de/organization/bafu"
            )

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
        error_msg = await _handle_tool_error("env_bafu_datasets", e, ctx, query=params.query)
        raise _terminal_failure(
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
@trace_tool
async def env_bafu_dataset_detail(
    params: BafuDatasetDetailInput, ctx: Context | None = None
) -> str:
    """
    Ruft vollständige Metadaten und Download-URLs eines BAFU-Datensatzes ab.

    Liefert: Titel, Beschreibung, Ressourcen mit Direktlinks (CSV, JSON, WMS/WFS),
    Lizenz, Aktualisierungsintervall und Kontaktinformationen.

    <use_case>Vollständige Metadaten + Download-URLs eines konkreten Datensatzes.</use_case>
    <important_notes>dataset_id/Slug zuerst via `env_bafu_datasets` ermitteln.</important_notes>

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
        desc_text = (
            (desc.get("de") or desc.get("en") or "") if isinstance(desc, dict) else str(desc)
        )
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
            r_label = (
                (r_name.get("de") or r_name.get("en") or "")
                if isinstance(r_name, dict)
                else str(r_name)
            )
            r_format = r.get("format", "–")
            r_url = r.get("download_url", r.get("url", "–"))
            lines.append(f"- **{r_label}** ({r_format}): {r_url}")

        lines += [
            "",
            f"**opendata.swiss:** https://opendata.swiss/de/dataset/{params.dataset_id}",
        ]
        return "\n".join(lines)

    except Exception as e:
        error_msg = await _handle_tool_error(
            "env_bafu_dataset_detail", e, ctx, dataset_id=params.dataset_id
        )
        raise _terminal_failure(
            f"⚠️ Datensatz '{params.dataset_id}' nicht gefunden: {error_msg}\n\n"
            "**Tipp:** Nutze `env_bafu_datasets` um gültige Dataset-IDs zu finden.\n"
            "**BAFU-Datenkatalog:** https://opendata.swiss/de/organization/bafu"
        )


# --- Resources ----------------------------------------------------------------


@mcp.resource("env://grenzwerte/luft")
async def get_air_limits() -> str:
    """Schweizer LRV-Grenzwerte und WHO 2021-Richtwerte für Luftschadstoffe."""
    data = {
        "schweizer_lrv": {k: {"wert": v, "einheit": "µg/m³"} for k, v in SWISS_LRV_LIMITS.items()},
        "who_2021": {k: {"wert": v, "einheit": "µg/m³"} for k, v in WHO_2021_LIMITS.items()},
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


def build_cors_app(origins: list[str] | None = None):
    """Streamable-HTTP-App mit CORS-Middleware (Audit SDK-004).

    Browser-/SSE-Clients müssen den `Mcp-Session-Id`-Header lesen können
    (`expose_headers`) und in Folge-Requests senden dürfen (`allow_headers`).
    `allow_origins` ist konfigurierbar (MCP_CORS_ALLOW_ORIGINS); in Produktion
    eine explizite Liste statt der `*`-Wildcard verwenden.
    """
    from starlette.middleware.cors import CORSMiddleware

    origins = origins if origins is not None else settings.cors_origins()
    if origins == ["*"]:
        logger.warning(
            "cors_wildcard_origin",
            detail="MCP_CORS_ALLOW_ORIGINS='*' — in Produktion auf explizite Origins setzen",
        )
    return CORSMiddleware(
        mcp.streamable_http_app(),
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*", "Mcp-Session-Id"],
        expose_headers=["Mcp-Session-Id"],
        # Keine Auth/Credentials in diesem Server -> False (zulässig mit "*").
        allow_credentials=False,
    )


def main() -> None:
    # Transport via Settings (Env-Vars). Default ist stdio (Audit SEC-006).
    transport = settings.mcp_transport.replace("_", "-")

    if transport == "streamable-http":
        # Host/Port am FastMCP-Konstruktor gesetzt; hier synchronisieren.
        mcp.settings.host = settings.mcp_host
        mcp.settings.port = settings.port
        import uvicorn

        uvicorn.run(
            build_cors_app(),
            host=settings.mcp_host,
            port=settings.port,
            log_level="info",
        )
    elif transport == "sse":
        mcp.settings.host = settings.mcp_host
        mcp.settings.port = settings.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
