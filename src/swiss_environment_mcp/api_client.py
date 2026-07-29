"""
HTTP-Client für BAFU-Datenquellen.

Quellen:
  - hydrodaten.admin.ch  – Hydrologische Mess- und Warnungsdaten
  - opendata.swiss        – BAFU-Datensätze (CKAN API)
  - naturgefahren.ch      – Naturgefahren-Bulletin (SLF/BAFU)
  - waldbrandgefahr.ch    – Waldbrandgefahr Schweiz
  - map.bafu.admin.ch     – BAFU Web-GIS (Gefahrenkarten)
  - api3.geo.admin.ch     – BAZL-Fluglärmbelastungskataster (identify)

Sicherheit (siehe Audit SEC-004 / SEC-021):
  - Egress-Allow-List auf Code-Ebene (nur die fest definierten Gov-Hosts)
  - HTTPS wird vor jedem Request erzwungen
  - Aufgelöste IPs werden gegen private/link-local/loopback geprüft (SSRF)
  - follow_redirects=False — kein Redirect auf interne Ziele

Der HTTP-Client ist ein einzelner, wiederverwendeter AsyncClient (siehe
Audit SDK-001). Er wird über startup()/shutdown() im MCPServer-Lifespan
verwaltet, statt pro Tool-Call neu erzeugt zu werden.
"""

import html as html_lib
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from . import USER_AGENT, geoadmin, sparql_client
from .lindas import client as lindas_client
from .logging_setup import get_logger

# Debug-Stufe: ausgehende Upstream-Requests (nur mit LOG_LEVEL=DEBUG sichtbar,
# Audit OBS-003). Der Correlation-Kontext (request_id/tool) wird vom Tool-Layer
# via structlog-contextvars gebunden und erscheint hier automatisch mit.
_logger = get_logger(component="api_client")

# --- Basis-URLs ---------------------------------------------------------------

HYDRO_BASE = "https://www.hydrodaten.admin.ch"
HYDRO_JSON_BASE = f"{HYDRO_BASE}/lhg/az/json"
HYDRO_XML_STATIONS = f"{HYDRO_BASE}/lhg/az/xml/hydroweb.xml"

OPENDATA_SWISS_API = "https://opendata.swiss/api/3/action"

# naturgefahren.ch wird nicht mehr per HTTP kontaktiert (API stillgelegt, s.u.);
# die Domain erscheint nur noch als Text-Link in der Tool-Ausgabe und ist daher
# aus der Egress-Allow-List entfernt (SEC-021, Angriffsfläche minimieren).

WALDBRAND_BASE = "https://www.waldbrandgefahr.ch"

BAFU_WEB = "https://www.bafu.admin.ch"
BAFU_GIS = "https://map.bafu.admin.ch"

# --- LINDAS (Linked Data Service des Bundes) — SPARQL -------------------------
# Aktuelle hydrologische Messwerte des BAFU als RDF-Data-Cube (cube.link).
# Transport seit Phase 2 der Hydro-Erweiterung über das extraktionsfähige
# Modul `lindas/` (client.py: GET/POST, 45-s-Client-Timeout, QueryError für
# HTTP 400 MALFORMED, Retry 2 s/4 s/8 s nur bei transienten Fehlern).
LINDAS_ENDPOINT = lindas_client.LINDAS_ENDPOINT
LINDAS_HYDRO_GRAPH = "https://lindas.admin.ch/foen/hydro"
_HYDRO_STATION_CLASS = "http://example.com/HydroMeasuringStation"
_HYDRO_DIM = "https://environment.ld.admin.ch/foen/hydro/dimension/"

# Retry-Parameter für den geteilten JSON-Client (siehe sparql_client).
# 4xx (ausser 429) sind deterministisch → sofort durchreichen. Diese Werte werden
# bei jedem Aufruf an sparql_client übergeben (Tests monkeypatchen RETRY_BASE_DELAY).
RETRY_MAX_ATTEMPTS = sparql_client.DEFAULT_MAX_ATTEMPTS
RETRY_BASE_DELAY = sparql_client.DEFAULT_BASE_DELAY  # Sekunden. Tests setzen 0.

# LINDAS-Retry (Portfolio-Standard 2 s/4 s/8 s; Tests setzen die Delay auf 0).
LINDAS_RETRY_MAX_ATTEMPTS = lindas_client.DEFAULT_MAX_ATTEMPTS
LINDAS_RETRY_BASE_DELAY = lindas_client.DEFAULT_BASE_DELAY

# --- SLF-Datenservice (WSL) — öffentliche No-Auth-APIs, CC BY 4.0 -------------
# Schnee (Schneehöhe/Neuschnee) + Lawinenbulletin. Niederschlag bewusst NICHT
# angebunden (Zuständigkeitsmatrix: Niederschlag = meteoswiss-mcp).
SLF_MEASUREMENT_API = "https://measurement-api.slf.ch/public/api"
SLF_BULLETIN_API = "https://aws.slf.ch/api/bulletin"

# --- Eidg. Jagdstatistik (BAFU) — content-negotiiertes JSON-Backend ----------
# Undokumentierter Vertrag: dieselbe Seiten-URL liefert JSON statt HTML, wenn der
# AJAX-Header gesetzt ist. Fragil (Highcharts-zentriert) → Schema-Guard im Tool.
JAGD_STATISTICS_URL = "https://www.jagdstatistik.ch/de/statistics"
JAGD_AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

# --- geo.admin.ch (BAZL-Fluglärmbelastungskataster) ---------------------------
# Punktabfragen gegen den identify-Endpoint der Bundes-Geodaten-Infrastruktur.
# Transport und Fachlogik liegen im extraktionsfähigen Modul `geoadmin.py`
# (analog `lindas/`); hier nur die dünne Bindung an den geteilten Client und
# den Egress-Guard. Retry: 2 s/4 s/8 s (Tests monkeypatchen auf 0).
GEOADMIN_HOST = geoadmin.GEOADMIN_HOST
GEOADMIN_RETRY_MAX_ATTEMPTS = geoadmin.RETRY_MAX_ATTEMPTS
GEOADMIN_RETRY_BASE_DELAY = geoadmin.RETRY_BASE_DELAY

TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Egress-Allow-List (Code-Layer, Audit SEC-021). Nur diese Hosts dürfen
# kontaktiert werden — frozenset, damit zur Laufzeit nicht mutierbar.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "www.hydrodaten.admin.ch",
        "opendata.swiss",
        "www.waldbrandgefahr.ch",
        "www.bafu.admin.ch",
        "map.bafu.admin.ch",
        "lindas.admin.ch",
        "measurement-api.slf.ch",
        "aws.slf.ch",
        "www.jagdstatistik.ch",
        geoadmin.GEOADMIN_HOST,
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
    """Validiert eine Ziel-URL gegen Schema- und Allow-List-Regeln.

    Wird vor *jedem* ausgehenden Request aufgerufen (auch als `egress_check`-
    Callback der SPARQL-/JSON-Clients).

    Die IP-/SSRF-Prüfung (DNS-Auflösung + Blocklist) erfolgt bewusst **nicht**
    hier, sondern **einmalig** im `_PinnedTransport` unmittelbar vor dem Connect
    (Audit SEC-005): So gibt es genau *eine* DNS-Resolution pro Request und kein
    TOCTOU-Fenster zwischen Prüfung und Verbindungsaufbau. Früher löste diese
    Funktion zusätzlich auf → zwei `getaddrinfo`-Calls pro Request.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SecurityError(f"Nur HTTPS-Requests erlaubt (war: '{parsed.scheme}')")
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS:
        raise SecurityError(f"Host '{host}' ist nicht in der Egress-Allow-List")


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
    """Erstellt einen konfigurierten AsyncClient mit DNS-Pinning-Transport.

    Der User-Agent kommt aus `__init__.USER_AGENT` und damit aus den
    Paket-Metadaten — hier steht bewusst keine Versionsnummer mehr.
    """
    return httpx.AsyncClient(
        transport=_PinnedTransport(),
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
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
    _logger.debug("upstream_request", method="GET", url=url)
    client = get_client()
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response


def handle_http_error(e: Exception) -> str:
    """Einheitliche Fehlerformatierung für alle Tools."""
    if isinstance(e, SecurityError):
        return f"Fehler: Anfrage durch Sicherheitsrichtlinie blockiert ({e})."
    if isinstance(e, lindas_client.QueryError):
        # Die MALFORMED-Meldung benennt die fehlerhafte Query-Stelle — sie wird
        # bewusst durchgereicht statt maskiert (Auftrag Phase 2; kein Leak von
        # Server-Interna, die Meldung stammt vom öffentlichen SPARQL-Endpoint).
        return f"Fehler: LINDAS hat die Abfrage abgelehnt (HTTP {e.status_code}): {e}"
    if isinstance(e, lindas_client.QueryTimeoutError):
        return f"Fehler: {e}"
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


# --- LINDAS SPARQL-Client (Transport: lindas/client.py) -----------------------


# SPARQL-Helfer aus dem wiederverwendbaren Modul re-exportiert (Rückwärtskompat.).
sparql_escape = sparql_client.sparql_escape


async def run_sparql(query: str) -> list[dict[str, str]]:
    """Führt eine SPARQL-Abfrage gegen den LINDAS-Endpoint aus (flache Dicts).

    Dünne Bindung an `lindas.client.select` (Egress-Guard, GET/POST, 45-s-
    Timeout, QueryError bei 400, Retry 2 s/4 s/8 s). Erfüllt die
    `lindas.cube.SelectRunner`-Signatur und wird von den Tools als Runner an
    die Cube-Schicht übergeben. `LINDAS_RETRY_BASE_DELAY` wird zur Laufzeit
    gelesen (Tests monkeypatchen auf 0).
    """
    _logger.debug("upstream_request", method="SPARQL", url=LINDAS_ENDPOINT)
    return await lindas_client.select(
        get_client(),
        query,
        endpoint=LINDAS_ENDPOINT,
        base_delay=LINDAS_RETRY_BASE_DELAY,
        max_attempts=LINDAS_RETRY_MAX_ATTEMPTS,
        egress_check=assert_host_allowed,
    )


async def fetch_hydro_stations_lindas() -> list[dict[str, Any]]:
    """Ruft alle hydrologischen Messstationen via LINDAS-SPARQL ab.

    Liefert typisierte Stationsmetadaten (id = BAFU-Stationsnummer, Name,
    Gewässer) statt des fragilen JSON-Scrapings von hydrodaten.admin.ch.
    """
    query = f"""
PREFIX s: <http://schema.org/>
SELECT ?id ?name ?water
FROM <{LINDAS_HYDRO_GRAPH}>
WHERE {{
  ?st a <{_HYDRO_STATION_CLASS}> ;
      s:identifier ?id ;
      s:name ?name .
  OPTIONAL {{
    ?st s:containedInPlace ?wb .
    BIND(REPLACE(STR(?wb), ".*/waterbody/", "") AS ?water)
  }}
}}
"""
    rows = await run_sparql(query)
    stations: list[dict[str, Any]] = []
    for r in rows:
        stations.append(
            {
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "water": unquote(r.get("water", "")),
            }
        )
    return stations


async def fetch_hydro_warnings_lindas(min_level: int = 2) -> list[dict[str, Any]]:
    """Ruft aktuelle Hochwasser-/Gefahrenwarnungen via LINDAS-SPARQL ab.

    Ersetzt den stillgelegten REST-Endpoint `hydrodaten.admin.ch/.../warnings.json`
    (404). Nutzt die `dangerLevel`-Dimension des Hydro-Cubes; `cube.link/Undefined`
    wird über `isNumeric` herausgefiltert.
    """
    query = f"""
PREFIX s: <http://schema.org/>
PREFIX hd: <{_HYDRO_DIM}>
SELECT ?id ?name ?water ?danger ?level ?discharge ?time
FROM <{LINDAS_HYDRO_GRAPH}>
WHERE {{
  ?st a <{_HYDRO_STATION_CLASS}> ;
      s:identifier ?id ;
      s:name ?name .
  OPTIONAL {{
    ?st s:containedInPlace ?wb .
    BIND(REPLACE(STR(?wb), ".*/waterbody/", "") AS ?water)
  }}
  ?obs hd:station ?st ;
       hd:dangerLevel ?danger ;
       hd:measurementTime ?time .
  OPTIONAL {{ ?obs hd:waterLevel ?level }}
  OPTIONAL {{ ?obs hd:discharge ?discharge }}
  FILTER(isNumeric(?danger) && ?danger >= {int(min_level)})
}}
"""
    rows = await run_sparql(query)
    warnings: list[dict[str, Any]] = []
    for r in rows:
        warnings.append(
            {
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "water": unquote(r.get("water", "")),
                "danger_level": int(float(r.get("danger") or "0")),
                "level": r.get("level") or None,
                "discharge": r.get("discharge") or None,
                "time": r.get("time", ""),
            }
        )
    warnings.sort(key=lambda w: w["danger_level"], reverse=True)
    return warnings


async def fetch_hydro_current_lindas(station_id: str) -> dict[str, Any]:
    """Ruft den aktuellen Messwert einer Station via LINDAS-SPARQL ab.

    Liefert Pegel (m ü.M.), Abfluss (m³/s), Wassertemperatur (°C) und
    Gefahrenstufe als typisierte Werte. `found` ist False, wenn die Station-ID
    im Graph nicht existiert (⇒ Aufrufer kann auf REST zurückfallen).
    """
    sid = sparql_escape(station_id)
    query = f"""
PREFIX s: <http://schema.org/>
PREFIX hd: <{_HYDRO_DIM}>
SELECT ?name ?water ?time ?level ?discharge ?temp ?danger
FROM <{LINDAS_HYDRO_GRAPH}>
WHERE {{
  ?st a <{_HYDRO_STATION_CLASS}> ;
      s:identifier ?id ;
      s:name ?name .
  # schema:identifier ist xsd:integer → über STR() datentyp-robust vergleichen.
  FILTER(STR(?id) = "{sid}")
  OPTIONAL {{
    ?st s:containedInPlace ?wb .
    BIND(REPLACE(STR(?wb), ".*/waterbody/", "") AS ?water)
  }}
  ?obs hd:station ?st ;
       hd:measurementTime ?time .
  OPTIONAL {{ ?obs hd:waterLevel ?level }}
  OPTIONAL {{ ?obs hd:discharge ?discharge }}
  OPTIONAL {{ ?obs hd:waterTemperature ?temp }}
  OPTIONAL {{ ?obs hd:dangerLevel ?danger }}
}}
LIMIT 1
"""
    rows = await run_sparql(query)
    if not rows:
        return {"found": False, "station_id": station_id}
    r = rows[0]
    danger_raw = r.get("danger", "")
    # dangerLevel ist entweder eine Zahl 1–5 oder cube.link/Undefined.
    danger = danger_raw if danger_raw and "Undefined" not in danger_raw else None
    return {
        "found": True,
        "station_id": station_id,
        "name": r.get("name", ""),
        "water": unquote(r.get("water", "")),
        "time": r.get("time", ""),
        "level": r.get("level") or None,
        "discharge": r.get("discharge") or None,
        "temperature": r.get("temp") or None,
        "danger_level": danger,
    }


# --- Hydrodaten-Client --------------------------------------------------------


async def fetch_hydro_stations() -> dict[str, Any]:
    """Ruft die Liste aller aktiven BAFU-Hydromesstationen ab."""
    response = await _get_json(f"{HYDRO_JSON_BASE}/mobile_stations.json")
    return response.json()


async def fetch_hydro_station_data(station_id: str) -> dict[str, Any]:
    """Ruft aktuelle Messwerte für eine einzelne Messstation ab."""
    response = await _get_json(f"{HYDRO_JSON_BASE}/{station_id}.json")
    return response.json()


# Hinweis: Die früheren REST-Fetcher `fetch_hydro_warnings` (warnings.json) und
# `fetch_hydro_station_history` (Hydrological_Data.csv) wurden entfernt — beide
# Endpoints unter hydrodaten.admin.ch/lhg/az/* sind stillgelegt (404). Ersatz:
# LINDAS (`fetch_hydro_warnings_lindas`) bzw. der Abfragezentrale-Bezugsweg in
# `env_hydro_history`.


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


# --- Naturgefahren -------------------------------------------------------------
# Die früheren REST-Fetcher (`fetch_hazard_overview` / `fetch_regional_hazards`)
# wurden entfernt: die aggregierte naturgefahren.ch-Warnungs-API ist stillgelegt
# (2026, 301→404) und es existiert kein stabiler, dokumentierter öffentlicher
# Ersatz-Feed (MeteoSchweiz-OGD/STAC, opendata.swiss, App-API — alle geprüft, s.
# docs/probe-naturgefahren-hazards.md). Die Tools env_hazard_overview /
# env_hazard_regions sind daher netzwerkfreie Orientierungs-/Routing-Tools; die
# einzelnen Gefahren liefern die dedizierten Tools (Hochwasser via LINDAS,
# Lawine/Schnee via SLF, Waldbrand via waldbrandgefahr.ch).


# --- Waldbrand-Client ---------------------------------------------------------


# Regex, um den `data-react-props`-Block der waldbrandgefahr.ch-Startseite zu
# extrahieren (undokumentierter Rails/ActiveStorage-Vertrag, siehe Docstring).
_WB_REACT_PROPS = re.compile(r'data-react-props="([^"]+)"')


async def fetch_wildfire_danger(language: str = "de") -> dict[str, Any]:
    """Ruft die aktuelle Waldbrandgefahr je Region ab (Zwei-Schritt-Zugriff).

    **Fundstück 2026-07-26:** Der frühere REST-Endpoint
    `waldbrandgefahr.ch/api/danger` ist stillgelegt (404). Die Seite ist neu
    eine Rails/React-App **ohne stabile JSON-API**: die aktuellen
    Gefahrenstufen liegen unter einer *signierten* ActiveStorage-Blob-URL, deren
    Pfad (Feld `warnMapJsonPath`) samt Kanton-Mapping (`cantons`) im
    `data-react-props`-Attribut der Startseite steht. Zugriff daher zweistufig:
    Startseite laden → `data-react-props` parsen → Blob-JSON laden.

    Undokumentierter, HTML-getragener Vertrag → Schema-Guard: `found=False`,
    wenn die erwartete Struktur fehlt (Aufrufer degradiert dann graceful).

    Returns:
        Normalisiertes Dict `{"found": True, "regions": [...]}` mit je Region
        `name`, `canton` (Kürzel), `danger_level` (1–5), `valid_from` — oder
        `{"found": False}`.
    """
    # 1) Startseite laden und die eingebetteten React-Props parsen.
    home = await _get_json(f"{WALDBRAND_BASE}/")
    match = _WB_REACT_PROPS.search(home.text)
    if not match:
        return {"found": False}
    try:
        props = json.loads(html_lib.unescape(match.group(1)))
    except (ValueError, TypeError):
        return {"found": False}

    json_path = props.get("warnMapJsonPath")
    cantons = props.get("cantons")
    if not isinstance(json_path, str) or not isinstance(cantons, list):
        return {"found": False}

    # canton_id → Kürzel (aus den React-Props, z.B. 4 → "BE", 24 → "VS").
    canton_by_id = {c.get("id"): c.get("abbr") for c in cantons if isinstance(c, dict)}

    # 2) Blob-JSON mit den Gefahrenstufen laden (gleicher, erlaubter Host).
    blob_url = json_path if json_path.startswith("http") else f"{WALDBRAND_BASE}{json_path}"
    blob = await _get_json(blob_url)
    rows = blob.json()
    if not isinstance(rows, list):
        return {"found": False}

    lang = language if language in {"de", "fr", "it", "en"} else "de"
    regions: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict) or "level" not in r:
            continue
        name = r.get(f"region_name_{lang}") or r.get("region_name_de") or "–"
        regions.append(
            {
                "name": name,
                "canton": canton_by_id.get(r.get("canton_id"), "–"),
                "danger_level": int(r.get("level") or 0),
                "valid_from": r.get("valid_from"),
            }
        )
    return {"found": True, "regions": regions}


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


# --- SLF-Client (Schnee & Lawinen) --------------------------------------------


async def _get_json_retry(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET-JSON mit Egress-Guard + Retry (dünne Bindung an sparql_client)."""
    _logger.debug("upstream_request", method="GET", url=url)
    return await sparql_client.get_json(
        get_client(),
        url,
        params=params,
        headers=headers,
        base_delay=RETRY_BASE_DELAY,
        max_attempts=RETRY_MAX_ATTEMPTS,
        egress_check=assert_host_allowed,
    )


async def fetch_slf_snow_stations() -> list[dict[str, Any]]:
    """Ruft die automatischen IMIS-Messstationen des SLF ab (Metadaten).

    Felder je Station: code, label, lon, lat, elevation (m), country_code,
    canton_code, type (z.B. SNOW_FLAT, WIND).
    """
    data = await _get_json_retry(f"{SLF_MEASUREMENT_API}/imis/stations")
    return data if isinstance(data, list) else []


async def fetch_slf_daily_snow() -> list[dict[str, Any]]:
    """Ruft die Tages-Schneewerte aller IMIS-Stationen ab.

    Felder: station_code, measure_date (UTC), HS (Schneehöhe, cm),
    HN_1D (Neuschnee 24 h, cm). Ein Call liefert alle Stationen (batch-fähig).
    """
    data = await _get_json_retry(f"{SLF_MEASUREMENT_API}/imis/daily-snow")
    return data if isinstance(data, list) else []


async def fetch_slf_avalanche_bulletin(language: str = "de") -> dict[str, Any]:
    """Ruft das aktuelle Lawinenbulletin als CAAML-GeoJSON ab.

    Liefert eine FeatureCollection (je Warnregion ein Feature). Ausserhalb der
    Lawinensaison ist `features` leer — das ist kein Fehler, sondern der reguläre
    Saisonzyklus (kein aktives Bulletin).
    """
    lang = language if language in {"de", "fr", "it", "en"} else "de"
    data = await _get_json_retry(f"{SLF_BULLETIN_API}/caaml/{lang}/geojson")
    return data if isinstance(data, dict) else {"type": "FeatureCollection", "features": []}


# --- Jagdstatistik-Client -----------------------------------------------------


async def fetch_jagd_statistics(species: str, datatype: str, canton: str) -> dict[str, Any]:
    """Ruft eine Auswertung der Eidg. Jagdstatistik ab (content-negotiiertes JSON).

    Args:
        species: `sp`-Code der Tierart (z.B. '2' für Reh).
        datatype: `th`-Code (1=Abschuss, 2=Bestand, 3=Aussetzung, 4=Fallwild).
        canton: `ar`-Code (Kantonskürzel oder 'CH' für die ganze Schweiz).

    Returns:
        Normalisiertes Dict mit title/subtitle/years/series oder `found=False`,
        falls das erwartete Highcharts-Control fehlt (Schema-Guard).
    """
    params = {"tt": "0", "sp": species, "th": datatype, "ar": canton}
    data = await _get_json_retry(JAGD_STATISTICS_URL, params=params, headers=JAGD_AJAX_HEADERS)

    # Schema-Guard: undokumentierter, Highcharts-zentrierter Vertrag (siehe
    # docs/probe-jagdstatistik.md). Ändert sich die Struktur, greift dieser Pfad.
    control = (data or {}).get("controls", {}).get("fi-chart-or-table", {})
    cd = control.get("ctrldata")
    if not isinstance(cd, dict) or "series" not in cd:
        return {"found": False}

    years = cd.get("xAxis", {}).get("categories", [])
    series: list[dict[str, Any]] = []
    for s in cd.get("series", []):
        # Highcharts-Werte kommen als [[v], [v], …] oder [v, v, …] → flach ziehen.
        values = [v[0] if isinstance(v, list) and v else v for v in s.get("data", [])]
        series.append({"name": s.get("name", "–"), "values": values})

    return {
        "found": True,
        "title": cd.get("title", {}).get("text", ""),
        "subtitle": cd.get("subtitle", {}).get("text", ""),
        "years": years,
        "series": series,
    }


# --- Fluglärmbelastungskataster (BAZL via geo.admin.ch) -----------------------
#
# Architektur-Entscheid: **Live-API statt Dump** (siehe README «Architektur-
# Entscheid»). Nicht aus Grössengründen — der gesamte Kataster umfasst 747
# Objekte (~3 MB) und wäre ohne Weiteres spiegelbar. Ausschlaggebend ist, dass
# die Kataster je Flugplatz einzeln und unangekündigt nachgeführt werden
# (Gültigkeitsdaten 2009–2024): ein Spiegel würde die `validfrom`-Angabe in
# `source_freshness` entwerten und die Auslegung amtlicher Lärmkurven aus dem
# Bundesamt in diesen Server verlagern.

# Zeitpunkt des letzten erfolgreichen Abrufs je Periode — ausschliesslich für
# den degraded-Envelope (Graceful Degradation). Bewusst **kein Datencache**:
# gespeichert wird nur der Zeitstempel, nie ein Messwert oder eine Kurve.
_geoadmin_last_success: dict[str, str] = {}


def geoadmin_last_success(period: str) -> str | None:
    """Letzter erfolgreicher Abruf für eine Periode (ISO-8601-UTC) oder None."""
    return _geoadmin_last_success.get(period)


def _note_geoadmin_success(period: str) -> None:
    _geoadmin_last_success[period] = geoadmin.utc_now()


async def fetch_aircraft_noise(
    period: str,
    east: int,
    north: int,
    radius_m: int = geoadmin.DEFAULT_RADIUS_M,
) -> dict[str, Any]:
    """Fluglärmbelastung an einem LV95-Punkt (BAZL-Kataster via identify)."""
    _logger.debug("upstream_request", method="GET", url=geoadmin.IDENTIFY_URL, period=period)
    result = await geoadmin.noise_at_point(
        get_client(),
        period=period,
        east=east,
        north=north,
        radius_m=radius_m,
        egress_check=assert_host_allowed,
        base_delay=GEOADMIN_RETRY_BASE_DELAY,
        max_attempts=GEOADMIN_RETRY_MAX_ATTEMPTS,
    )
    _note_geoadmin_success(period)
    return result


async def fetch_aircraft_noise_registers(
    period: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Übersicht der publizierten Lärmbelastungskataster (Provenienz-Abfrage)."""
    _logger.debug("upstream_request", method="GET", url=geoadmin.IDENTIFY_URL, period=period)
    entries = await geoadmin.registers(
        get_client(),
        period=period,
        limit=limit,
        egress_check=assert_host_allowed,
        base_delay=GEOADMIN_RETRY_BASE_DELAY,
        max_attempts=GEOADMIN_RETRY_MAX_ATTEMPTS,
    )
    _note_geoadmin_success(period or "*")
    return entries
