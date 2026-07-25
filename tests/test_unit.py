"""
Mocked Unit-Tests für swiss-environment-mcp (Audit OPS-001).

Diese Tests laufen OHNE Netzwerk: alle ausgehenden httpx-Requests werden mit
`respx` gemockt. Sie sind die Standard-CI-Suite (`pytest -m "not live"`).
Live-Tests gegen echte BAFU-APIs stehen in tests/test_integration.py (Marker `live`).
"""

import os
import sys

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp import api_client as api  # noqa: E402
from swiss_environment_mcp.server import (  # noqa: E402
    AirLimitsCheckInput,
    AvalancheBulletinInput,
    BafuDatasetsInput,
    FloodWarningsInput,
    HuntingSpeciesInput,
    HuntingStatsInput,
    HydroCurrentInput,
    HydroStationsInput,
    NabelCurrentInput,
    NabelStationsInput,
    ResponseFormat,
    SnowCurrentInput,
    SnowStationsInput,
    env_air_limits_check,
    env_avalanche_bulletin,
    env_bafu_datasets,
    env_flood_warnings,
    env_hunting_species,
    env_hunting_stats,
    env_hydro_current,
    env_hydro_stations,
    env_nabel_current,
    env_nabel_stations,
    env_snow_current,
    env_snow_stations,
    health,
)


@pytest.fixture(autouse=True)
async def _reset_client():
    """Frischen geteilten Client je Test, sauber schliessen (SDK-001).

    DNS-Pinning (SEC-005) wird in Tests deaktiviert, damit die respx-Mocks
    nicht durch die URL-zu-IP-Umschreibung umgangen werden.
    """
    api.dns_pin_enabled = False
    await api.shutdown()
    yield
    await api.shutdown()
    api.dns_pin_enabled = True


# --- Reine Logik (kein Netzwerk) ----------------------------------------------


async def test_air_limits_exceeded():
    out = await env_air_limits_check(
        AirLimitsCheckInput(pollutant="NO2", value=45.0, averaging_period="annual")
    )
    assert "NO2" in out
    assert "ÜBERSCHRITTEN" in out  # 45 > LRV-Grenzwert 30


async def test_air_limits_within():
    out = await env_air_limits_check(AirLimitsCheckInput(pollutant="PM10", value=5.0))
    assert "Eingehalten" in out


async def test_air_limits_unknown_pollutant():
    out = await env_air_limits_check(AirLimitsCheckInput(pollutant="XYZ", value=1.0))
    assert "nicht erkannt" in out


async def test_nabel_stations_markdown_offline():
    """env_nabel_stations nutzt nur lokale Konstanten — kein Netzwerk nötig."""
    out = await env_nabel_stations(NabelStationsInput(response_format=ResponseFormat.MARKDOWN))
    assert "NABEL" in out and "ZUE" in out


async def test_nabel_unknown_station():
    out = await env_nabel_current(NabelCurrentInput(station="XXX"))
    assert "nicht gefunden" in out


# --- Gemockte HTTP-Pfade (respx) ----------------------------------------------


@respx.mock
async def test_bafu_datasets_mocked():
    respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "count": 1,
                    "results": [
                        {
                            "name": "nabel-test",
                            "title": {"de": "NABEL Testdatensatz"},
                            "notes": {"de": "Beschreibung"},
                            "metadata_modified": "2026-01-01T00:00:00",
                        }
                    ],
                }
            },
        )
    )
    out = await env_bafu_datasets(BafuDatasetsInput(query="luft", rows=5))
    assert "NABEL Testdatensatz" in out
    assert "1 Datensätze gefunden" in out


@respx.mock
async def test_hydro_stations_fallback_on_error():
    """Bei API-Fehler liefert das Tool den dokumentierten Fallback (ARCH-003)."""
    respx.get("https://www.hydrodaten.admin.ch/lhg/az/json/mobile_stations.json").mock(
        return_value=httpx.Response(503)
    )
    out = await env_hydro_stations(HydroStationsInput(canton="ZH"))
    assert "Live-API nicht erreichbar" in out
    assert "hydrodaten.admin.ch" in out


@respx.mock
async def test_flood_warnings_none_active():
    """Keine Station >= min_level (LINDAS liefert leere Bindings)."""
    respx.get(_LINDAS_URL).mock(return_value=httpx.Response(200, json=_sparql_bindings([])))
    out = await env_flood_warnings(FloodWarningsInput(min_level=2))
    assert "Keine aktiven Hochwasserwarnungen" in out


@respx.mock
async def test_flood_warnings_active_via_lindas():
    """Aktive Warnung (dangerLevel 3) wird aus LINDAS gelesen und gezeigt."""
    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [
                    {
                        "id": "2099",
                        "name": "Zürich Unterhard",
                        "water": "Limmat",
                        "danger": "3",
                        "level": "399.7",
                        "time": "t",
                    },
                ]
            ),
        )
    )
    out = await env_flood_warnings(FloodWarningsInput(min_level=2))
    assert "Zürich Unterhard" in out and "Erheblich" in out


# --- Sicherheits-Guard (SSRF / Egress, SEC-004 / SEC-021) ---------------------


def test_egress_blocks_unknown_host():
    with pytest.raises(api.SecurityError):
        api.assert_host_allowed("https://evil.example.com/x")


def test_egress_blocks_non_https():
    with pytest.raises(api.SecurityError):
        api.assert_host_allowed("http://opendata.swiss/api/3/action/package_search")


def test_egress_allows_listed_host():
    # Darf nicht werfen (IP-Resolution ist best-effort und offline-tolerant).
    api.assert_host_allowed("https://opendata.swiss/api/3/action/package_search")


@respx.mock
async def test_client_is_reused_singleton():
    """Geteilter Client statt neuer Client pro Call (SDK-001)."""
    await api.startup()
    c1 = api.get_client()
    c2 = api.get_client()
    assert c1 is c2


def test_dns_pin_blocks_internal_ip(monkeypatch):
    """DNS-Pin-Anker: aufgelöste interne IP wird blockiert (SEC-005)."""

    def fake_getaddrinfo(host, port, *a, **k):
        return [(2, 1, 6, "", ("169.254.169.254", 443))]

    monkeypatch.setattr(api.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(api.SecurityError):
        api._resolve_and_check("opendata.swiss")


def test_dns_pin_returns_public_ip(monkeypatch):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(2, 1, 6, "", ("185.27.134.1", 443))]

    monkeypatch.setattr(api.socket, "getaddrinfo", fake_getaddrinfo)
    assert api._resolve_and_check("opendata.swiss") == "185.27.134.1"


def test_client_uses_pinned_transport():
    c = api._new_client()
    assert isinstance(c._transport, api._PinnedTransport)


# --- Health-Endpoint (SCALE-004 / SEC-016) ------------------------------------


async def test_health_endpoint():
    from starlette.requests import Request

    scope = {"type": "http", "method": "GET", "headers": [], "path": "/health"}
    resp = await health(Request(scope))
    assert resp.status_code == 200
    assert b"ok" in resp.body


# --- Fehlerbehandlung / Observability (OBS-001 / OBS-002 / SDK-003) -----------


class _FakeContext:
    """Minimaler Context-Doppelgänger, der ctx.warning-Aufrufe sammelt."""

    def __init__(self):
        self.warnings: list[str] = []

    async def warning(self, msg: str) -> None:
        self.warnings.append(msg)


def test_error_detail_is_masked():
    """handle_http_error darf keine internen Details ans LLM leaken (OBS-002)."""
    msg = api.handle_http_error(ValueError("geheimes internes Detail xyz"))
    assert "geheimes internes Detail" not in msg
    assert "interner Fehler" in msg


@respx.mock
async def test_execution_error_path_logs_and_reports():
    """Execution-Error-Pfad: isError via ToolError, ctx.warning, strukturiertes Log (OBS-001).

    Seit v0.3.x wird ein terminaler Ausführungsfehler als `ToolError` geworfen —
    FastMCP setzt daraufhin `isError:true`. Die maskierte Meldung + der
    Direktzugang-Hinweis stehen im Fehler-Content; keine Internals leaken.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from structlog.testing import capture_logs

    from swiss_environment_mcp.server import env_bafu_datasets

    respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(500)
    )
    ctx = _FakeContext()
    with capture_logs() as logs:
        with pytest.raises(ToolError) as exc:
            await env_bafu_datasets(BafuDatasetsInput(query="x"), ctx=ctx)
    # Fehler-Content trägt den Fallback-Hinweis, aber keine Internals
    msg = str(exc.value)
    assert "fehlgeschlagen" in msg
    assert "Traceback" not in msg and "500 Internal" not in msg
    # Fehler wurde über den Context gemeldet ...
    assert ctx.warnings and "env_bafu_datasets" in ctx.warnings[0]
    # ... strukturiert geloggt (tool_error mit tool-Feld) ...
    assert any(
        e.get("event") == "tool_error" and e.get("tool") == "env_bafu_datasets" for e in logs
    )
    # ... und der Tool-Layer hat tool_failed (error-Stufe) emittiert (OBS-003).
    assert any(e.get("event") == "tool_failed" for e in logs)


async def test_protocol_error_invalid_args():
    """Protocol-Error-Pfad: ungültige Tool-Argumente -> ValidationError (OBS-001)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BafuDatasetsInput(rows=999)  # ueberschreitet le=50


# --- Input-Whitelisting (SEC-018) ---------------------------------------------


def test_station_id_rejects_non_numeric():
    from pydantic import ValidationError

    from swiss_environment_mcp.server import HydroCurrentInput

    with pytest.raises(ValidationError):
        HydroCurrentInput(station_id="2099; DROP TABLE")


def test_dataset_id_rejects_path_traversal():
    from pydantic import ValidationError

    from swiss_environment_mcp.server import BafuDatasetDetailInput

    with pytest.raises(ValidationError):
        BafuDatasetDetailInput(dataset_id="../../etc/passwd")


def test_station_accepts_lowercase_and_uppercases():
    out = NabelCurrentInput(station="zue")
    assert out.station == "ZUE"


# --- Tool-Snapshot / Rug-Pull-Schutz (SEC-022) --------------------------------


def test_tool_snapshot_is_current():
    """Committeter tool-snapshot.json muss den aktuellen Tool-Definitionen entsprechen."""
    import json
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from tool_snapshot import SNAPSHOT_PATH, build_snapshot

    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    current = build_snapshot()
    assert current["sha256"] == committed["sha256"], (
        "tool-snapshot.json ist veraltet — `python scripts/tool_snapshot.py` ausführen, "
        "CHANGELOG-Eintrag + Versions-Bump nicht vergessen (SEC-022)."
    )


# --- Response-Envelope & match_type (SDK-002 / ARCH-003) ----------------------


async def test_nabel_stations_json_envelope():
    """JSON-Modus liefert den typisierten Envelope (SDK-002)."""
    import json

    out = await env_nabel_stations(NabelStationsInput(response_format=ResponseFormat.JSON))
    env = json.loads(out)
    assert set(["source", "provenance", "count", "match_type", "results"]) <= env.keys()
    assert env["count"] == 16 and env["match_type"] == "exact"
    assert env["count"] == len(env["results"])


@respx.mock
async def test_hydro_stations_json_match_type_none():
    """Leeres Filterresultat -> match_type 'none' + actionable note (ARCH-003)."""
    import json

    respx.get("https://www.hydrodaten.admin.ch/lhg/az/json/mobile_stations.json").mock(
        return_value=httpx.Response(200, json={"stations": []})
    )
    out = await env_hydro_stations(
        HydroStationsInput(canton="ZH", response_format=ResponseFormat.JSON)
    )
    env = json.loads(out)
    assert env["match_type"] == "none"
    assert env["count"] == 0
    assert env["note"] and "2099" in env["note"]


@respx.mock
async def test_bafu_datasets_json_envelope():
    """SDK-002: env_bafu_datasets liefert im JSON-Modus den typisierten Envelope."""
    import json

    respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(
            200, json={"result": {"count": 1, "results": [{"name": "x", "title": {"de": "X"}}]}}
        )
    )
    out = await env_bafu_datasets(
        BafuDatasetsInput(query="luft", response_format=ResponseFormat.JSON)
    )
    env = json.loads(out)
    assert env["source"].startswith("BAFU")
    assert env["count"] == 1 and env["match_type"] == "exact"
    assert env["count"] == len(env["results"])


@respx.mock
async def test_bafu_datasets_empty_note():
    """0 Treffer -> actionable Hinweis statt blanker Liste (ARCH-003)."""
    respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(200, json={"result": {"count": 0, "results": []}})
    )
    out = await env_bafu_datasets(BafuDatasetsInput(query="zzznotarealquery"))
    assert "match_type: none" in out
    assert "0 Treffer" in out


# --- Use-Case-Tags in Tool-Descriptions (ARCH-002) ----------------------------


async def test_all_tools_have_use_case_tag():
    from swiss_environment_mcp.server import mcp

    tools = await mcp.list_tools()
    assert len(tools) == 18
    missing = [t.name for t in tools if "<use_case>" not in (t.description or "")]
    assert not missing, f"Tools ohne <use_case>-Tag: {missing}"


# --- CORS / Mcp-Session-Id (SDK-004) ------------------------------------------


def test_tracing_creates_tool_span(monkeypatch):
    """OBS-006: ein Tool-Call erzeugt einen Span mit mcp.tool.name + is_error."""
    pytest.importorskip("opentelemetry.sdk")
    import asyncio

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from swiss_environment_mcp import tracing
    from swiss_environment_mcp.server import AirLimitsCheckInput, env_air_limits_check

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    monkeypatch.setattr(tracing, "_TRACING_ON", True)

    asyncio.run(env_air_limits_check(AirLimitsCheckInput(pollutant="NO2", value=45.0)))

    spans = exporter.get_finished_spans()
    assert any(s.name == "mcp.tool.env_air_limits_check" for s in spans)
    span = next(s for s in spans if s.name == "mcp.tool.env_air_limits_check")
    assert span.attributes["mcp.tool.name"] == "env_air_limits_check"
    assert span.attributes["mcp.tool.result.is_error"] is False


def test_cors_exposes_and_allows_session_id_header():
    """HTTP-Transport exponiert Mcp-Session-Id via CORS für Browser-Clients."""
    from starlette.testclient import TestClient

    from swiss_environment_mcp.server import build_cors_app

    origin = "https://example.com"
    app = build_cors_app(origins=[origin])
    with TestClient(app) as client:
        # Aktuelle Response: expose-headers enthält Mcp-Session-Id
        resp = client.get("/health", headers={"Origin": origin})
        assert resp.status_code == 200
        assert "Mcp-Session-Id" in resp.headers.get("access-control-expose-headers", "")

        # Preflight: expliziter Origin wird gespiegelt (keine Wildcard), Header erlaubt
        pre = client.options(
            "/mcp",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "mcp-session-id",
            },
        )
        assert pre.headers.get("access-control-allow-origin") == origin
        assert "mcp-session-id" in pre.headers.get("access-control-allow-headers", "").lower()


# --- LINDAS SPARQL-Pfad (Hydro, Phase 3) --------------------------------------

_LINDAS_URL = "https://lindas.admin.ch/query"


def _sparql_bindings(rows: list[dict]) -> dict:
    """Baut eine SPARQL-results+json-Antwort aus einfachen {key: value}-Zeilen."""
    return {
        "results": {"bindings": [{k: {"value": str(v)} for k, v in row.items()} for row in rows]}
    }


@respx.mock
async def test_hydro_current_lindas_happy():
    """env_hydro_current nutzt primär LINDAS und zeigt typisierte Live-Werte."""
    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [
                    {
                        "name": "Zürich Unterhard",
                        "water": "Limmat",
                        "time": "2026-07-19T14:20:00+01:00",
                        "discharge": "34.997",
                        "level": "399.716",
                    }
                ]
            ),
        )
    )
    out = await env_hydro_current(HydroCurrentInput(station_id="2099"))
    assert "Limmat" in out
    assert "34.997" in out
    assert "Abfluss" in out
    assert "LINDAS" in out


@respx.mock
async def test_hydro_current_lindas_json_provenance():
    """JSON-Modus liefert provenance 'live_api' für den LINDAS-Pfad."""
    import json

    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [{"name": "Zürich Unterhard", "water": "Limmat", "time": "t", "discharge": "34.9"}]
            ),
        )
    )
    out = await env_hydro_current(
        HydroCurrentInput(station_id="2099", response_format=ResponseFormat.JSON)
    )
    data = json.loads(out)
    assert data["provenance"] == "live_api"
    assert data["gewaesser"] == "Limmat"


@respx.mock
async def test_hydro_current_lindas_retry_then_success(monkeypatch):
    """Transienter 503 wird retried; zweiter Versuch erfolgreich (Resilienz)."""
    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    route = respx.get(_LINDAS_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(
                200,
                json=_sparql_bindings(
                    [
                        {
                            "name": "Zürich Unterhard",
                            "water": "Limmat",
                            "time": "t",
                            "discharge": "34.9",
                        }
                    ]
                ),
            ),
        ]
    )
    out = await env_hydro_current(HydroCurrentInput(station_id="2099"))
    assert route.call_count == 2
    assert "34.9" in out


@respx.mock
async def test_hydro_current_lindas_timeout_falls_back_to_rest(monkeypatch):
    """LINDAS-Totalausfall → sauberer Fallback auf den REST-Pfad."""
    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    respx.get(_LINDAS_URL).mock(side_effect=httpx.ConnectError("boom"))
    respx.get("https://www.hydrodaten.admin.ch/lhg/az/json/2099.json").mock(
        return_value=httpx.Response(
            200,
            json={"name": "Limmat REST", "water_body_name": "Limmat", "parameters": []},
        )
    )
    out = await env_hydro_current(HydroCurrentInput(station_id="2099"))
    assert "Limmat REST" in out  # REST-Pfad hat übernommen


@respx.mock
async def test_hydro_stations_lindas_water_body_filter():
    """env_hydro_stations (ohne Kanton) nutzt LINDAS und filtert nach Gewässer."""
    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [
                    {"id": "2099", "name": "Zürich Unterhard", "water": "Limmat"},
                    {"id": "2243", "name": "Baden, Limmatpromenade", "water": "Limmat"},
                    {"id": "2030", "name": "Basel", "water": "Rhein"},
                ]
            ),
        )
    )
    out = await env_hydro_stations(HydroStationsInput(water_body="Limmat"))
    assert "2099" in out and "2243" in out
    assert "2030" not in out  # Rhein herausgefiltert
    assert "LINDAS" in out


@respx.mock
async def test_run_sparql_400_no_retry(monkeypatch):
    """Deterministischer 400 → QueryError MIT MALFORMED-Meldung, ohne Retry."""
    from swiss_environment_mcp.lindas import client as lindas_client

    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    route = respx.get(_LINDAS_URL).mock(return_value=httpx.Response(400, text="MALFORMED"))
    with pytest.raises(lindas_client.QueryError, match="MALFORMED"):
        await api.run_sparql("SELECT ?x WHERE { ?x")
    assert route.call_count == 1  # kein Retry bei 4xx


def test_lindas_host_is_allowed():
    """LINDAS-Endpoint steht auf der Egress-Allow-List (Phase 3)."""
    api.assert_host_allowed(api.LINDAS_ENDPOINT)


# --- SLF Schnee & Lawinen (Phase 3, Inkrement 2) ------------------------------

_SLF_STATIONS_URL = "https://measurement-api.slf.ch/public/api/imis/stations"
_SLF_SNOW_URL = "https://measurement-api.slf.ch/public/api/imis/daily-snow"
_SLF_BULLETIN_URL = "https://aws.slf.ch/api/bulletin/caaml/de/geojson"

_SLF_STATIONS = [
    {
        "code": "DAV2",
        "label": "Bärentälli",
        "canton_code": "GR",
        "elevation": 2558.0,
        "type": "SNOW_FLAT",
    },
    {
        "code": "TUM2",
        "label": "Val Miez",
        "canton_code": "GR",
        "elevation": 2191.0,
        "type": "SNOW_FLAT",
    },
    {
        "code": "ANV2",
        "label": "Anzonico",
        "canton_code": "TI",
        "elevation": 2000.0,
        "type": "SNOW_FLAT",
    },
]


@respx.mock
async def test_snow_stations_canton_filter():
    respx.get(_SLF_STATIONS_URL).mock(return_value=httpx.Response(200, json=_SLF_STATIONS))
    out = await env_snow_stations(SnowStationsInput(canton="GR"))
    assert "DAV2" in out and "TUM2" in out
    assert "ANV2" not in out  # TI herausgefiltert
    assert "CC BY 4.0" in out


@respx.mock
async def test_snow_current_join_and_sort():
    respx.get(_SLF_STATIONS_URL).mock(return_value=httpx.Response(200, json=_SLF_STATIONS))
    respx.get(_SLF_SNOW_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "station_code": "DAV2",
                    "measure_date": "2026-02-01T00:00:00",
                    "HS": 120.0,
                    "HN_1D": 15.0,
                },
                {
                    "station_code": "TUM2",
                    "measure_date": "2026-02-01T00:00:00",
                    "HS": 80.0,
                    "HN_1D": 5.0,
                },
                {
                    "station_code": "ANV2",
                    "measure_date": "2026-02-01T00:00:00",
                    "HS": 200.0,
                    "HN_1D": 0.0,
                },
            ],
        )
    )
    out = await env_snow_current(SnowCurrentInput(canton="GR"))
    assert "120.0" in out and "80.0" in out
    assert "ANV2" not in out  # TI herausgefiltert
    # DAV2 (HS 120) muss vor TUM2 (HS 80) stehen (Sortierung absteigend)
    assert out.index("DAV2") < out.index("TUM2")


@respx.mock
async def test_snow_current_retry_then_success(monkeypatch):
    monkeypatch.setattr(api, "RETRY_BASE_DELAY", 0)
    respx.get(_SLF_SNOW_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(
                200,
                json=[{"station_code": "DAV2", "measure_date": "d", "HS": 50.0, "HN_1D": 2.0}],
            ),
        ]
    )
    respx.get(_SLF_STATIONS_URL).mock(return_value=httpx.Response(200, json=_SLF_STATIONS))
    out = await env_snow_current(SnowCurrentInput(station="DAV2"))
    assert "50.0" in out


@respx.mock
async def test_avalanche_bulletin_offseason_empty():
    respx.get(_SLF_BULLETIN_URL).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    )
    out = await env_avalanche_bulletin(AvalancheBulletinInput(language="de"))
    assert "kein aktives Lawinenbulletin" in out.lower() or "kein aktives" in out


@respx.mock
async def test_avalanche_bulletin_winter_danger():
    """CAAML-Feature mit EAWS-Textwert 'considerable' → Stufe 3 (Erheblich)."""
    respx.get(_SLF_BULLETIN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "region": "Davos",
                            "dangerRatings": [{"mainValue": "considerable"}],
                        },
                    }
                ],
            },
        )
    )
    out = await env_avalanche_bulletin(AvalancheBulletinInput(language="de"))
    assert "Davos" in out
    assert "Stufe 3" in out and "Erheblich" in out


def test_slf_hosts_allowed():
    api.assert_host_allowed(_SLF_STATIONS_URL)
    api.assert_host_allowed(_SLF_BULLETIN_URL)


# --- Jagdstatistik (Phase 3, Inkrement 3) -------------------------------------

_JAGD_URL = "https://www.jagdstatistik.ch/de/statistics"


def _jagd_chart(years, series):
    """Baut eine Jagdstatistik-Antwort (controls → Highcharts-ctrldata)."""
    return {
        "controls": {
            "fi-chart-or-table": {
                "ctrltype": "bs4chart",
                "ctrldata": {
                    "title": {"text": "Testart, 2015 bis 2024"},
                    "subtitle": {"text": "Abschuss, Zürich"},
                    "xAxis": {"categories": years},
                    "series": [{"name": n, "data": [[v] for v in vals]} for n, vals in series],
                },
            }
        }
    }


async def test_hunting_species_local():
    """env_hunting_species ist rein lokal (kein Netzwerk) und listet alle Arten."""
    out = await env_hunting_species(HuntingSpeciesInput())
    assert "Reh" in out and "Rothirsch" in out
    assert "36 Arten" in out


@respx.mock
async def test_hunting_stats_happy():
    respx.get(_JAGD_URL).mock(
        return_value=httpx.Response(
            200,
            json=_jagd_chart(["2015", "2016"], [("Kitz", [10, 20]), ("Bock", [5, 7])]),
        )
    )
    out = await env_hunting_stats(
        HuntingStatsInput(species="Reh", canton="ZH", data_type="abschuss")
    )
    assert "Reh" in out and "Abschuss" in out
    assert "15" in out and "27" in out  # Totals je Jahr (10+5, 20+7)


@respx.mock
async def test_hunting_stats_species_by_code():
    respx.get(_JAGD_URL).mock(
        return_value=httpx.Response(200, json=_jagd_chart(["2015"], [("Total", [42])]))
    )
    out = await env_hunting_stats(HuntingStatsInput(species="1", canton="GR", data_type="fallwild"))
    assert "Rothirsch" in out and "42" in out


async def test_hunting_stats_unknown_species():
    out = await env_hunting_stats(HuntingStatsInput(species="Einhorn", canton="CH"))
    assert "nicht erkannt" in out


@respx.mock
async def test_hunting_stats_schema_guard():
    """Fehlt das erwartete Chart-Control, greift die Graceful Degradation."""
    respx.get(_JAGD_URL).mock(
        return_value=httpx.Response(
            200, json={"controls": {"ja-news": {"ctrltype": "bs4messages"}}}
        )
    )
    out = await env_hunting_stats(HuntingStatsInput(species="Reh", canton="ZH"))
    assert "nicht ausgelesen" in out


@respx.mock
async def test_hunting_stats_retry_then_success(monkeypatch):
    monkeypatch.setattr(api, "RETRY_BASE_DELAY", 0)
    route = respx.get(_JAGD_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=_jagd_chart(["2015"], [("Total", [99])])),
        ]
    )
    out = await env_hunting_stats(HuntingStatsInput(species="Reh", canton="ZH"))
    assert route.call_count == 2
    assert "99" in out


def test_jagd_host_allowed():
    api.assert_host_allowed(_JAGD_URL)


# --- Wiederverwendbarer sparql_client (Portfolio-Baustein) --------------------

from swiss_environment_mcp import sparql_client as sc  # noqa: E402

_SC_URL = "https://example.test/query"


def test_sparql_escape_reused():
    assert sc.sparql_escape('a"b\\c') == 'a\\"b\\\\c'
    assert api.sparql_escape is sc.sparql_escape  # api_client re-exportiert


@respx.mock
async def test_sc_get_bindings_happy():
    respx.get(_SC_URL).mock(return_value=httpx.Response(200, json=_sparql_bindings([{"x": "1"}])))
    async with httpx.AsyncClient() as c:
        b = await sc.get_bindings(c, _SC_URL, "SELECT ?x {}")
    assert sc.binding_val(b[0], "x") == "1"


@respx.mock
async def test_sc_retry_on_503():
    route = respx.get(_SC_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_sparql_bindings([]))]
    )
    async with httpx.AsyncClient() as c:
        await sc.get_bindings(c, _SC_URL, "q", base_delay=0)
    assert route.call_count == 2


@respx.mock
async def test_sc_no_retry_on_400():
    route = respx.get(_SC_URL).mock(return_value=httpx.Response(400))
    async with httpx.AsyncClient() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await sc.get_bindings(c, _SC_URL, "q", base_delay=0)
    assert route.call_count == 1


async def test_sc_egress_check_blocks():
    def block(url):
        raise api.SecurityError("blocked")

    async with httpx.AsyncClient() as c:
        with pytest.raises(api.SecurityError):
            await sc.get_bindings(c, _SC_URL, "q", egress_check=block)
