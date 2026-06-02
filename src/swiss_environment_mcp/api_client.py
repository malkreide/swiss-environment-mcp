"""
HTTP-Client für BAFU-Datenquellen.

Quellen:
  - hydrodaten.admin.ch  – Hydrologische Mess- und Warnungsdaten
  - opendata.swiss        – BAFU-Datensätze (CKAN API)
  - naturgefahren.ch      – Naturgefahren-Bulletin (SLF/BAFU)
  - waldbrandgefahr.ch    – Waldbrandgefahr Schweiz
  - map.bafu.admin.ch     – BAFU Web-GIS (Gefahrenkarten)

Sicherheit (siehe Audit SEC-004 / SEC-021):
  - Egress-Allow-List auf Code-Ebene (nur die fest definierten Gov-Hosts)
  - HTTPS wird vor jedem Request erzwungen
  - Aufgelöste IPs werden gegen private/link-local/loopback geprüft (SSRF)
  - follow_redirects=False — kein Redirect auf interne Ziele

Der HTTP-Client ist ein einzelner, wiederverwendeter AsyncClient (siehe
Audit SDK-001). Er wird über startup()/shutdown() im FastMCP-Lifespan
verwaltet, statt pro Tool-Call neu erzeugt zu werden.
"""

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

# --- Basis-URLs ---------------------------------------------------------------

HYDRO_BASE = "https://www.hydrodaten.admin.ch"
HYDRO_JSON_BASE = f"{HYDRO_BASE}/lhg/az/json"
HYDRO_XML_STATIONS = f"{HYDRO_BASE}/lhg/az/xml/hydroweb.xml"

OPENDATA_SWISS_API = "https://opendata.swiss/api/3/action"

NATURGEFAHREN_BASE = "https://www.naturgefahren.ch"
NATURGEFAHREN_API = f"{NATURGEFAHREN_BASE}/api"

WALDBRAND_BASE = "https://www.waldbrandgefahr.ch"

BAFU_WEB = "https://www.bafu.admin.ch"
BAFU_GIS = "https://map.bafu.admin.ch"

TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Egress-Allow-List (Code-Layer, Audit SEC-021). Nur diese Hosts dürfen
# kontaktiert werden — frozenset, damit zur Laufzeit nicht mutierbar.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "www.hydrodaten.admin.ch",
        "opendata.swiss",
        "www.naturgefahren.ch",
        "www.waldbrandgefahr.ch",
        "www.bafu.admin.ch",
        "map.bafu.admin.ch",
    }
)


class SecurityError(Exception):
    """Ausgehender Request verletzt die Egress-/SSRF-Richtlinie."""


# --- Egress-Guard (SSRF-Schutz, Audit SEC-004) --------------------------------

# DNS-Pinning aktiv (Audit SEC-005). In der Test-Suite deaktiviert, damit das
# respx-Mocking nicht durch URL-zu-IP-Umschreibung umgangen wird.
dns_pin_enabled = True


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve_and_check(host: str) -> str | None:
    """Löst den Host **einmalig** auf, blockt interne IPs und liefert die erste
    öffentliche IP zurück (DNS-Pin-Anker, Audit SEC-004/SEC-005).

    Best-effort: Schlägt die Auflösung fehl (z.B. offline), wird nicht blockiert
    und None zurückgegeben — der httpx-Connect scheitert dann ohnehin sauber.
    """
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None
    first: str | None = None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise SecurityError(f"Aufgelöste IP {ip} für Host '{host}' ist blockiert (SSRF-Schutz)")
        if first is None:
            first = str(ip)
    return first


def assert_host_allowed(url: str) -> None:
    """Validiert eine Ziel-URL gegen Schema-, Allow-List- und IP-Regeln.

    Wird vor *jedem* ausgehenden Request aufgerufen.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SecurityError(f"Nur HTTPS-Requests erlaubt (war: '{parsed.scheme}')")
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS:
        raise SecurityError(f"Host '{host}' ist nicht in der Egress-Allow-List")
    _resolve_and_check(host)


class _PinnedTransport(httpx.AsyncHTTPTransport):
    """DNS-Pinning-Transport (Audit SEC-005).

    Löst den Hostnamen einmalig auf, prüft die IP gegen die Blocklist und
    verbindet sich mit genau dieser IP — während SNI und Zertifikatsprüfung
    weiterhin gegen den Original-Hostnamen laufen (`sni_hostname`). Damit gibt
    es kein TOCTOU-Fenster zwischen Prüfung und Connect (DNS-Rebinding).
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if dns_pin_enabled and request.url.scheme == "https" and host:
            ip = _resolve_and_check(host)  # SecurityError propagiert (Block)
            if ip:
                request.extensions = {**request.extensions, "sni_hostname": host}
                # Host-Header bleibt der Original-Hostname; nur das Connect-Ziel
                # wird auf die gepinnte IP gesetzt.
                request.url = request.url.copy_with(host=ip)
        return await super().handle_async_request(request)


# --- Geteilter HTTP-Client (Lifecycle via Lifespan, Audit SDK-001) ------------

_client: httpx.AsyncClient | None = None


def _new_client() -> httpx.AsyncClient:
    """Erstellt einen konfigurierten AsyncClient mit DNS-Pinning-Transport."""
    return httpx.AsyncClient(
        transport=_PinnedTransport(),
        timeout=TIMEOUT,
        headers={
            "User-Agent": "swiss-environment-mcp/0.1.0 (https://github.com/malkreide/swiss-environment-mcp)",
            "Accept": "application/json, application/xml, */*",
        },
        follow_redirects=False,
    )


def get_client() -> httpx.AsyncClient:
    """Liefert den geteilten AsyncClient (lazy erzeugt, einmalig)."""
    global _client
    if _client is None or _client.is_closed:
        _client = _new_client()
    return _client


async def startup() -> None:
    """Initialisiert den geteilten Client (vom Lifespan aufgerufen)."""
    get_client()


async def shutdown() -> None:
    """Schliesst den geteilten Client (vom Lifespan aufgerufen)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def _get_json(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """Gemeinsamer GET-Pfad: Egress-Guard + geteilter Client + raise_for_status."""
    assert_host_allowed(url)
    client = get_client()
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response


def handle_http_error(e: Exception) -> str:
    """Einheitliche Fehlerformatierung für alle Tools."""
    if isinstance(e, SecurityError):
        return f"Fehler: Anfrage durch Sicherheitsrichtlinie blockiert ({e})."
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
    # Keine internen Details (Exception-Typ/-Text) ans LLM leaken (Audit OBS-002).
    # Der konkrete Fehler wird serverseitig strukturiert geloggt.
    return "Fehler: Unerwarteter interner Fehler. Bitte erneut versuchen."


# --- Hydrodaten-Client --------------------------------------------------------


async def fetch_hydro_stations() -> dict[str, Any]:
    """Ruft die Liste aller aktiven BAFU-Hydromesstationen ab."""
    response = await _get_json(f"{HYDRO_JSON_BASE}/mobile_stations.json")
    return response.json()


async def fetch_hydro_station_data(station_id: str) -> dict[str, Any]:
    """Ruft aktuelle Messwerte für eine einzelne Messstation ab."""
    response = await _get_json(f"{HYDRO_JSON_BASE}/{station_id}.json")
    return response.json()


async def fetch_hydro_warnings() -> dict[str, Any]:
    """Ruft aktuelle Hochwasserwarnungen aller Messstationen ab."""
    response = await _get_json(f"{HYDRO_JSON_BASE}/warnings.json")
    return response.json()


async def fetch_hydro_station_history(
    station_id: str,
    parameter: str,
    days: int = 7,
) -> dict[str, Any]:
    """Ruft historische Stundenwerte einer Messstation ab."""
    params = {
        "station": station_id,
        "parameter": parameter,
        "period": f"P{days}D",
        "format": "json",
    }
    response = await _get_json(f"{HYDRO_BASE}/lhg/az/csv/Hydrological_Data.csv", params=params)
    return {"raw": response.text, "station": station_id, "days": days}


# --- opendata.swiss CKAN-Client -----------------------------------------------


async def search_bafu_datasets(
    query: str = "",
    rows: int = 10,
    start: int = 0,
) -> dict[str, Any]:
    """Sucht BAFU-Datensätze auf opendata.swiss via CKAN-API."""
    params: dict[str, Any] = {
        "q": query,
        "fq": "organization:bafu",
        "rows": rows,
        "start": start,
        "sort": "score desc, metadata_modified desc",
    }
    response = await _get_json(f"{OPENDATA_SWISS_API}/package_search", params=params)
    return response.json()


async def get_bafu_dataset(dataset_id: str) -> dict[str, Any]:
    """Ruft die vollständigen Metadaten eines BAFU-Datensatzes ab."""
    response = await _get_json(f"{OPENDATA_SWISS_API}/package_show", params={"id": dataset_id})
    return response.json()


# --- Naturgefahren-Client -----------------------------------------------------


async def fetch_hazard_overview(language: str = "de") -> dict[str, Any]:
    """Ruft das aktuelle Naturgefahren-Bulletin der Schweiz ab."""
    response = await _get_json(
        f"{NATURGEFAHREN_API}/v1/warnings/overview/ch", params={"lang": language}
    )
    return response.json()


async def fetch_regional_hazards(region: str = "", language: str = "de") -> dict[str, Any]:
    """Ruft regionsspezifische Naturgefahrenwarnungen ab."""
    params: dict[str, Any] = {"lang": language}
    if region:
        params["region"] = region
    response = await _get_json(f"{NATURGEFAHREN_API}/v1/warnings/regions", params=params)
    return response.json()


# --- Waldbrand-Client ---------------------------------------------------------


async def fetch_wildfire_danger(language: str = "de") -> dict[str, Any]:
    """Ruft die aktuelle Waldbrandgefahr nach Regionen ab."""
    response = await _get_json(f"{WALDBRAND_BASE}/api/danger", params={"lang": language})
    return response.json()


# --- BAFU Webseite (Luftqualität/NABEL) ---------------------------------------


async def fetch_nabel_stations() -> dict[str, Any]:
    """Ruft die Metadaten der 16 NABEL-Messstationen von opendata.swiss ab."""
    response = await _get_json(
        f"{OPENDATA_SWISS_API}/package_show",
        params={"id": "nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"},
    )
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
    params: dict[str, Any] = {
        "q": f"NABEL {station_abbreviation} {parameter}",
        "fq": "organization:bafu",
        "rows": 5,
    }
    response = await _get_json(f"{OPENDATA_SWISS_API}/package_search", params=params)
    return response.json()
