"""
HTTP-Client für BAFU-Datenquellen.

Quellen:
  - hydrodaten.admin.ch  – Hydrologische Mess- und Warnungsdaten
  - opendata.swiss        – BAFU-Datensätze (CKAN API)
  - naturgefahren.ch      – Naturgefahren-Bulletin (SLF/BAFU)
  - waldbrandgefahr.ch    – Waldbrandgefahr Schweiz
  - map.bafu.admin.ch     – BAFU Web-GIS (Gefahrenkarten)
"""

from typing import Any

import httpx

# --- Basis-URLs ---------------------------------------------------------------

HYDRO_BASE         = "https://www.hydrodaten.admin.ch"
HYDRO_JSON_BASE    = f"{HYDRO_BASE}/lhg/az/json"
HYDRO_XML_STATIONS = f"{HYDRO_BASE}/lhg/az/xml/hydroweb.xml"

OPENDATA_SWISS_API = "https://opendata.swiss/api/3/action"

NATURGEFAHREN_BASE = "https://www.naturgefahren.ch"
NATURGEFAHREN_API  = f"{NATURGEFAHREN_BASE}/api"

WALDBRAND_BASE     = "https://www.waldbrandgefahr.ch"

BAFU_WEB           = "https://www.bafu.admin.ch"
BAFU_GIS           = "https://map.bafu.admin.ch"

TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# --- Hilfsfunktionen ----------------------------------------------------------

def _make_client() -> httpx.AsyncClient:
    """Erstellt einen konfigurierten AsyncClient mit Standard-Headers."""
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        headers={
            "User-Agent": "swiss-environment-mcp/0.1.0 (https://github.com/malkreide/swiss-environment-mcp)",
            "Accept": "application/json, application/xml, */*",
        },
        follow_redirects=True,
    )


def handle_http_error(e: Exception) -> str:
    """Einheitliche Fehlerformatierung für alle Tools."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return "Fehler: Ressource nicht gefunden. Bitte Eingabeparameter prüfen."
        if code == 429:
            return "Fehler: Rate-Limit überschritten. Bitte kurz warten."
        if code == 503:
            return "Fehler: Dienst vorübergehend nicht verfügbar. Bitte später erneut versuchen."
        return f"Fehler: API-Anfrage fehlgeschlagen (HTTP {code})."
    if isinstance(e, httpx.TimeoutException):
        return "Fehler: Anfrage-Timeout. Der Server antwortet nicht. Bitte erneut versuchen."
    if isinstance(e, httpx.ConnectError):
        return "Fehler: Verbindung nicht möglich. Netzwerkverbindung oder Dienststatus prüfen."
    return f"Fehler: Unerwarteter Fehler ({type(e).__name__}): {e}"


# --- Hydrodaten-Client --------------------------------------------------------

async def fetch_hydro_stations() -> dict[str, Any]:
    """Ruft die Liste aller aktiven BAFU-Hydromesstationen ab."""
    async with _make_client() as client:
        # Öffentlicher JSON-Endpoint mit Stationsliste
        response = await client.get(f"{HYDRO_JSON_BASE}/mobile_stations.json")
        response.raise_for_status()
        return response.json()


async def fetch_hydro_station_data(station_id: str) -> dict[str, Any]:
    """Ruft aktuelle Messwerte für eine einzelne Messstation ab."""
    async with _make_client() as client:
        response = await client.get(f"{HYDRO_JSON_BASE}/{station_id}.json")
        response.raise_for_status()
        return response.json()


async def fetch_hydro_warnings() -> dict[str, Any]:
    """Ruft aktuelle Hochwasserwarnungen aller Messstationen ab."""
    async with _make_client() as client:
        response = await client.get(f"{HYDRO_JSON_BASE}/warnings.json")
        response.raise_for_status()
        return response.json()


async def fetch_hydro_station_history(
    station_id: str,
    parameter: str,
    days: int = 7,
) -> dict[str, Any]:
    """Ruft historische Stundenwerte einer Messstation ab."""
    async with _make_client() as client:
        # CSV-Endpoint für historische Daten
        params = {
            "station": station_id,
            "parameter": parameter,
            "period": f"P{days}D",
            "format": "json",
        }
        response = await client.get(
            f"{HYDRO_BASE}/lhg/az/csv/Hydrological_Data.csv",
            params=params,
        )
        response.raise_for_status()
        return {"raw": response.text, "station": station_id, "days": days}


# --- opendata.swiss CKAN-Client -----------------------------------------------

async def search_bafu_datasets(
    query: str = "",
    rows: int = 10,
    start: int = 0,
) -> dict[str, Any]:
    """Sucht BAFU-Datensätze auf opendata.swiss via CKAN-API."""
    async with _make_client() as client:
        params: dict[str, Any] = {
            "q": query,
            "fq": "organization:bafu",
            "rows": rows,
            "start": start,
            "sort": "score desc, metadata_modified desc",
        }
        response = await client.get(
            f"{OPENDATA_SWISS_API}/package_search",
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def get_bafu_dataset(dataset_id: str) -> dict[str, Any]:
    """Ruft die vollständigen Metadaten eines BAFU-Datensatzes ab."""
    async with _make_client() as client:
        response = await client.get(
            f"{OPENDATA_SWISS_API}/package_show",
            params={"id": dataset_id},
        )
        response.raise_for_status()
        return response.json()


# --- Naturgefahren-Client -----------------------------------------------------

async def fetch_hazard_overview(language: str = "de") -> dict[str, Any]:
    """Ruft das aktuelle Naturgefahren-Bulletin der Schweiz ab."""
    async with _make_client() as client:
        # Öffentliche JSON-API von naturgefahren.ch (SLF/BAFU)
        response = await client.get(
            f"{NATURGEFAHREN_API}/v1/warnings/overview/ch",
            params={"lang": language},
        )
        response.raise_for_status()
        return response.json()


async def fetch_regional_hazards(region: str = "", language: str = "de") -> dict[str, Any]:
    """Ruft regionsspezifische Naturgefahrenwarnungen ab."""
    async with _make_client() as client:
        params: dict[str, Any] = {"lang": language}
        if region:
            params["region"] = region
        response = await client.get(
            f"{NATURGEFAHREN_API}/v1/warnings/regions",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# --- Waldbrand-Client ---------------------------------------------------------

async def fetch_wildfire_danger(language: str = "de") -> dict[str, Any]:
    """Ruft die aktuelle Waldbrandgefahr nach Regionen ab."""
    async with _make_client() as client:
        # waldbrandgefahr.ch publiziert eine JSON-API für die interaktive Karte
        response = await client.get(
            f"{WALDBRAND_BASE}/api/danger",
            params={"lang": language},
        )
        response.raise_for_status()
        return response.json()


# --- BAFU Webseite (Luftqualität/NABEL) ---------------------------------------

async def fetch_nabel_stations() -> dict[str, Any]:
    """Ruft die Metadaten der 16 NABEL-Messstationen von opendata.swiss ab."""
    async with _make_client() as client:
        # NABEL-Stationsdaten sind auf opendata.swiss verfügbar
        response = await client.get(
            f"{OPENDATA_SWISS_API}/package_show",
            params={"id": "nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_nabel_data(
    station_abbreviation: str,
    parameter: str = "NO2",
    year: int | None = None,
) -> dict[str, Any]:
    """
    Ruft Luftqualitätsmesswerte des NABEL ab.

    NABEL-Daten sind via opendata.swiss als downloadbare Ressourcen verfügbar.
    Diese Funktion gibt die Metadaten inkl. Download-URLs zurück.
    """
    async with _make_client() as client:
        params: dict[str, Any] = {
            "q": f"NABEL {station_abbreviation} {parameter}",
            "fq": "organization:bafu",
            "rows": 5,
        }
        response = await client.get(
            f"{OPENDATA_SWISS_API}/package_search",
            params=params,
        )
        response.raise_for_status()
        return response.json()
