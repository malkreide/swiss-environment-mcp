"""
Mocked Unit-Tests für swiss-environment-mcp (Audit OPS-001).

Diese Tests laufen OHNE Netzwerk: alle ausgehenden httpx-Requests werden mit
`respx` gemockt. Sie sind die Standard-CI-Suite (`pytest -m "not live"`).
Live-Tests gegen echte BAFU-APIs stehen in tests/test_integration.py (Marker `live`).
"""

import json
import os
import sys
import tomllib

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import swiss_environment_mcp  # noqa: E402
from swiss_environment_mcp import api_client as api  # noqa: E402
from swiss_environment_mcp.server import (  # noqa: E402
    AirLimitsCheckInput,
    AvalancheBulletinInput,
    BafuDatasetsInput,
    FloodWarningsInput,
    HazardOverviewInput,
    HazardRegionsInput,
    HuntingSpeciesInput,
    HuntingStatsInput,
    HydroCurrentInput,
    HydroStationsInput,
    NabelCurrentInput,
    NabelStationsInput,
    ResponseFormat,
    SnowCurrentInput,
    SnowStationsInput,
    WildfireDangerInput,
    env_air_limits_check,
    env_avalanche_bulletin,
    env_bafu_datasets,
    env_flood_warnings,
    env_hazard_overview,
    env_hazard_regions,
    env_hunting_species,
    env_hunting_stats,
    env_hydro_current,
    env_hydro_stations,
    env_nabel_current,
    env_nabel_stations,
    env_snow_current,
    env_snow_stations,
    env_wildfire_danger,
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
async def test_hydro_stations_fallback_on_error(monkeypatch):
    """Fällt LINDAS aus, liefert das Tool den dokumentierten Fallback (ARCH-003)."""
    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    respx.get(_LINDAS_URL).mock(return_value=httpx.Response(503))
    out = await env_hydro_stations(HydroStationsInput())
    assert "Live-API nicht erreichbar" in out
    assert "hydrodaten.admin.ch" in out
    # Die Liste muss sich als das zu erkennen geben, was sie ist.
    assert "kein Suchergebnis" in out


@respx.mock
async def test_hydro_stations_fallback_honours_json(monkeypatch):
    """Der Fallback ignorierte `response_format` und lieferte immer Markdown.

    Ein Client, der die Envelope angefordert hat, bekam ausgerechnet im
    Störungsfall Text — und `json.loads` scheiterte an der ⚠️-Zeile.
    """
    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    respx.get(_LINDAS_URL).mock(return_value=httpx.Response(503))
    env = json.loads(
        await env_hydro_stations(HydroStationsInput(response_format=ResponseFormat.JSON))
    )
    assert env["provenance"] == "fallback"
    assert env["match_type"] == "none"
    assert env["count"] == len(env["results"]) == 5
    assert "KEIN Suchergebnis" in env["note"]


@respx.mock
async def test_hydro_stations_canton_is_refused_not_faked():
    """Der Kantonsfilter sagt ab, statt die Beispielliste als Antwort auszugeben.

    Vorher lief jede Kantonsabfrage auf den stillgelegten REST-Endpoint (404)
    und landete im Fallback: für 'ZH' drei hartkodierte Stationen, die wie ein
    Suchergebnis aussahen. Kein Request darf dafür mehr rausgehen.
    """
    route = respx.get(_LINDAS_URL).mock(return_value=httpx.Response(200, json=_sparql_bindings([])))
    out = await env_hydro_stations(HydroStationsInput(canton="ZH"))
    assert route.call_count == 0, "Kantonsabfrage darf keine Live-Quelle mehr belasten"
    assert "Kantonsfilter nicht verfügbar" in out
    assert "water_body" in out
    # Keine der Beispielstationen darf als Treffer erscheinen.
    assert "2099" not in out and "Limmat – Zürich/Unterwerk" not in out


async def test_hydro_stations_canton_refusal_as_envelope():
    env = json.loads(
        await env_hydro_stations(
            HydroStationsInput(canton="BE", response_format=ResponseFormat.JSON)
        )
    )
    assert env["provenance"] == "unsupported_filter"
    assert env["match_type"] == "none" and env["count"] == 0
    # Die leere Liste darf nicht als «keine Stationen im Kanton» gelesen werden —
    # ohne dabei zu behaupten, es gebe dort welche: `canton` nimmt jeden Zwei-
    # Buchstaben-String, auch 'XX'. Die Antwort sagt, dass nicht gesucht wurde.
    assert "nicht gesucht" in env["note"]
    assert env["query"]["canton"] == "BE"


async def test_hydro_stations_refusal_claims_nothing_about_the_value():
    """`canton` ist nicht gegen die 26 Kantone validiert — 'XX' kommt durch.

    Die Absage darf deshalb keine Tatsachenbehauptung über den übergebenen Wert
    enthalten («dort gibt es Messstationen»), sondern nur über sich selbst.
    """
    out = await env_hydro_stations(HydroStationsInput(canton="XX"))
    assert "Es wurde nicht gesucht" in out
    assert "gibt es Messstationen" not in out


async def test_hydro_stations_canton_field_advertises_its_own_uselessness():
    """MCP-Clients lesen das Input-Schema, nicht den Docstring des Tools.

    Stünde in der Feld-Beschreibung weiter «Kantonskürzel zum Filtern», würden
    Modelle den Parameter wählen und eine Absage ernten.
    """
    field = HydroStationsInput.model_fields["canton"]
    assert "NICHT UNTERSTÜTZT" in field.description
    assert "water_body" in field.description


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


def test_assert_host_allowed_does_not_resolve(monkeypatch):
    """SEC-005: der Egress-Guard löst NICHT auf — die eine Resolution macht der Transport."""
    calls = {"n": 0}

    def counting(host, port, *a, **k):
        calls["n"] += 1
        return [(2, 1, 6, "", ("185.27.134.1", 443))]

    monkeypatch.setattr(api.socket, "getaddrinfo", counting)
    api.assert_host_allowed("https://opendata.swiss/api/3/action/package_search")
    assert calls["n"] == 0  # Schema+Allow-List only, keine DNS-Auflösung mehr


async def test_pinned_transport_resolves_once(monkeypatch):
    """SEC-005: genau EINE DNS-Resolution pro Request, im gepinnten Transport."""
    calls = {"n": 0}

    def counting(host, port, *a, **k):
        calls["n"] += 1
        return [(2, 1, 6, "", ("185.27.134.1", 443))]

    monkeypatch.setattr(api.socket, "getaddrinfo", counting)
    monkeypatch.setattr(api, "dns_pin_enabled", True)

    captured = {}

    async def fake_super(self, request):
        captured["host"] = request.url.host
        return httpx.Response(200, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_super)

    transport = api._PinnedTransport()
    resp = await transport.handle_async_request(httpx.Request("GET", "https://opendata.swiss/x"))
    assert resp.status_code == 200
    assert calls["n"] == 1  # exakt eine Resolution
    assert captured["host"] == "185.27.134.1"  # Connect-Ziel = gepinnte IP


# --- Versions-Herkunft: User-Agent aus den Paket-Metadaten --------------------


def test_user_agent_has_no_hardcoded_version():
    """Der UA-Header wird aus `__version__` gebaut, nicht als Literal gepflegt.

    Bis v0.5.1 stand die Nummer direkt im Header-Dict und musste bei jedem
    Release von Hand mitgezogen werden — dreimal ist das nachweislich
    vergessen worden (v0.2.0 → v0.5.0).
    """
    ua = api._new_client().headers["User-Agent"]
    assert ua == (
        f"swiss-environment-mcp/{swiss_environment_mcp.__version__} "
        "(https://github.com/malkreide/swiss-environment-mcp)"
    )


def test_version_matches_pyproject():
    """Die gemeldete Version ist die des Pakets — kein eigenständiger String."""
    if swiss_environment_mcp.__version__ == "0+unknown":
        pytest.skip("Paket nicht installiert (Quell-Checkout) — nichts zu vergleichen")

    with open(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"), "rb") as fh:
        expected = tomllib.load(fh)["project"]["version"]

    assert swiss_environment_mcp.__version__ == expected, (
        f"Installierte Metadaten melden {swiss_environment_mcp.__version__}, "
        f"pyproject.toml steht auf {expected}. Bei einem editable Install nach "
        "einem Versionsbump: `pip install -e .` erneut ausführen."
    )


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
    MCPServer setzt daraufhin `isError:true`. Die maskierte Meldung + der
    Direktzugang-Hinweis stehen im Fehler-Content; keine Internals leaken.
    """
    from mcp.server.mcpserver.exceptions import ToolError
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

    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200, json=_sparql_bindings([{"id": "2030", "name": "Basel", "water": "Rhein"}])
        )
    )
    out = await env_hydro_stations(
        HydroStationsInput(water_body="Gibtsnicht", response_format=ResponseFormat.JSON)
    )
    env = json.loads(out)
    assert env["match_type"] == "none"
    assert env["count"] == 0
    assert env["note"] and "Gibtsnicht" in env["note"]


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
    assert len(tools) == 21
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


# --- Naturgefahren & Waldbrand (OPS-001: Fehlerpfade in CI abgedeckt) ---------

# waldbrandgefahr.ch: Zwei-Schritt (Startseite → react-props → Blob-JSON).
_WILDFIRE_HOME_URL = "https://www.waldbrandgefahr.ch/"
_WILDFIRE_BLOB_PATH = "/rails/active_storage/blobs/proxy/signed-blob/fire_warn_levels.json"
_WILDFIRE_BLOB_URL = f"https://www.waldbrandgefahr.ch{_WILDFIRE_BLOB_PATH}"


def _wildfire_home_html() -> str:
    """Minimale Startseite mit dem `data-react-props`-Vertrag (Blob-Pfad + Kantone)."""
    import html as _h
    import json as _j

    props = {
        "warnMapJsonPath": _WILDFIRE_BLOB_PATH,
        "cantons": [
            {"id": 24, "name": "Wallis", "abbr": "VS"},
            {"id": 1, "name": "Aargau", "abbr": "AG"},
        ],
    }
    return f'<div data-react-props="{_h.escape(_j.dumps(props), quote=True)}"></div>'


def _wildfire_blob_rows() -> list:
    return [
        {"region_name_de": "Unterwallis", "canton_id": 24, "level": 4, "valid_from": "2026-07-20"},
        {"region_name_de": "Aaretal", "canton_id": 1, "level": 1, "valid_from": "2026-07-19"},
    ]


async def test_hazard_overview_is_network_free_router():
    """env_hazard_overview ist netzwerkfrei und routet auf die dedizierten Tools.

    Die aggregierte naturgefahren.ch-API ist stillgelegt; das Tool liefert eine
    deterministische Orientierung (Gefahr → zuständiges Tool) + Portallinks.
    Kein respx-Mock nötig — ein versehentlicher Netzwerk-Call würde ohne Mock
    unter respx/`assert_all_mocked` auffallen; hier genügt der Inhaltscheck.
    """
    out = await env_hazard_overview(HazardOverviewInput(language="de"))
    assert "env_flood_warnings" in out
    assert "env_avalanche_bulletin" in out
    assert "env_wildfire_danger" in out
    assert "meteoswiss-mcp" in out  # Wetterwarnungen sauber abgegrenzt
    assert "naturgefahren.ch" in out  # Portal-Link bleibt


async def test_hazard_regions_is_network_free_router():
    """env_hazard_regions echot die Region und routet auf die Live-Tools."""
    out = await env_hazard_regions(HazardRegionsInput(region="Graubünden"))
    assert "Graubünden" in out  # Region wird gespiegelt
    assert "env_wildfire_danger" in out and "canton=" in out
    assert "map.bafu.admin.ch" in out


@respx.mock
async def test_wildfire_danger_happy_filters_canton():
    """env_wildfire_danger: Zwei-Schritt-Zugriff, Stufe + Label, Kanton-Filter.

    canton_id 24 → 'VS' wird aus den react-props der Startseite aufgelöst.
    """
    respx.get(_WILDFIRE_HOME_URL).mock(return_value=httpx.Response(200, text=_wildfire_home_html()))
    respx.get(_WILDFIRE_BLOB_URL).mock(return_value=httpx.Response(200, json=_wildfire_blob_rows()))
    out = await env_wildfire_danger(WildfireDangerInput(language="de", canton="VS"))
    assert "Unterwallis" in out and "Stufe 4" in out and "Gross" in out
    assert "Aaretal" not in out  # Kantonsfilter greift (AG herausgefiltert)


@respx.mock
async def test_wildfire_danger_schema_guard_graceful():
    """Fehlt der react-props-Block, degradiert das Tool graceful (kein Crash)."""
    respx.get(_WILDFIRE_HOME_URL).mock(
        return_value=httpx.Response(200, text="<html>ohne props</html>")
    )
    out = await env_wildfire_danger(WildfireDangerInput(language="de"))
    assert "Traceback" not in out
    assert "waldbrandgefahr" in out  # Direktzugang bleibt


@respx.mock
async def test_wildfire_danger_error_raises_tool_error():
    from mcp.server.mcpserver.exceptions import ToolError

    respx.get(_WILDFIRE_HOME_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ToolError) as exc:
        await env_wildfire_danger(WildfireDangerInput(language="de"))
    assert "Waldbranddaten nicht abrufbar" in str(exc.value)


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


# --- Live-Marker: Transportfehler ist kein Vertragsbruch (conftest-Hook) ------
#
# Der nächtliche Live-Lauf scheiterte mehrfach an einem `httpx.ConnectTimeout`
# gegen `measurement-api.slf.ch`, obwohl dieselbe API kurz davor und danach
# antwortete. Der Hook in `conftest.py` stuft solche Läufe zu SKIPPED herab —
# aber nur sie. Die folgenden Tests halten beide Seiten dieser Grenze fest.

from conftest import (  # noqa: E402
    _UPSTREAM_SKIPS,
    _describe,
    _transport_cause,
    pytest_runtest_makereport,
)

_REQ = httpx.Request("GET", "https://measurement-api.slf.ch/public/api/imis/stations")


def test_transport_cause_direct():
    exc = httpx.ConnectTimeout("", request=_REQ)
    assert _transport_cause(exc) is exc


def test_transport_cause_walks_wrapping_chain():
    """Die Tools reichen den httpx-Fehler nicht durch, sie packen ihn ein."""
    try:
        try:
            raise httpx.ConnectError("nope", request=_REQ)
        except httpx.ConnectError as inner:
            raise RuntimeError("Tool-Fehler") from inner
    except RuntimeError as outer:
        found = _transport_cause(outer)
    assert isinstance(found, httpx.ConnectError)


def test_transport_cause_ignores_answered_requests():
    """HTTP 500 heisst: die Gegenstelle hat geantwortet — das ist ein Befund."""
    status = httpx.HTTPStatusError("HTTP 500", request=_REQ, response=httpx.Response(500))
    assert _transport_cause(status) is None
    assert _transport_cause(AssertionError("Schema kaputt")) is None
    assert _transport_cause(None) is None


def test_transport_cause_survives_exception_cycle():
    """Selbstbezügliche Ketten dürfen die Suche nicht endlos laufen lassen."""
    a = RuntimeError("a")
    b = RuntimeError("b")
    a.__context__ = b
    b.__context__ = a
    assert _transport_cause(a) is None


def test_describe_names_host_even_without_message():
    """`ConnectTimeout` trägt oft keine Meldung — dann trägt der Host sie."""
    text = _describe(httpx.ConnectTimeout("", request=_REQ))
    assert "measurement-api.slf.ch" in text
    assert "ConnectTimeout" in text


class _FakeReport:
    def __init__(self, when="call", failed=True):
        self.when = when
        self.failed = failed
        self.outcome = "failed"
        self.longrepr = "boom"


class _FakeExcInfo:
    def __init__(self, value):
        self.value = value


class _FakeCall:
    def __init__(self, value):
        self.excinfo = _FakeExcInfo(value) if value is not None else None


class _FakeItem:
    def __init__(self, *, live: bool):
        self._live = live
        self.path = "/repo/tests/test_integration.py"
        self.location = ("tests/test_integration.py", 228, "test_slf_snow")
        self.nodeid = "tests/test_integration.py::test_slf_snow"
        self.config = type("C", (), {"stash": pytest.Stash()})()

    def get_closest_marker(self, name):
        return pytest.mark.live if (self._live and name == "live") else None


def _run_hook(item, call, report):
    """Treibt den Wrapper-Hook von Hand: bis zum `yield`, dann Report hinein."""
    gen = pytest_runtest_makereport(item, call)
    next(gen)
    try:
        gen.send(report)
    except StopIteration as stop:
        return stop.value
    raise AssertionError("Hook hat nicht terminiert")


def test_hook_downgrades_live_transport_failure_to_skip():
    report = _FakeReport()
    item = _FakeItem(live=True)
    result = _run_hook(item, _FakeCall(httpx.ConnectTimeout("", request=_REQ)), report)
    assert result.outcome == "skipped"
    # 3-Tupel (Datei, Zeile, Meldung) — nur so stellt pytest einen Skip dar.
    assert isinstance(result.longrepr, tuple) and len(result.longrepr) == 3
    assert "measurement-api.slf.ch" in result.longrepr[2]
    assert item.config.stash.get(_UPSTREAM_SKIPS, [])


def test_hook_keeps_contract_failures_red():
    report = _FakeReport()
    result = _run_hook(_FakeItem(live=True), _FakeCall(AssertionError("Schema kaputt")), report)
    assert result.outcome == "failed"


def test_hook_ignores_tests_without_live_marker():
    """Ein Transportfehler im gemockten Lauf ist immer ein echter Fehler."""
    report = _FakeReport()
    result = _run_hook(
        _FakeItem(live=False), _FakeCall(httpx.ConnectTimeout("", request=_REQ)), report
    )
    assert result.outcome == "failed"


def test_hook_ignores_setup_and_teardown_phases():
    report = _FakeReport(when="teardown")
    result = _run_hook(
        _FakeItem(live=True), _FakeCall(httpx.ConnectTimeout("", request=_REQ)), report
    )
    assert result.outcome == "failed"


# --- CKAN-Organisationsfilter (opendata.swiss) -------------------------------
#
# `fq=organization:bafu` filterte jede Suche auf null Treffer: den Slug gibt es
# auf opendata.swiss nicht, und CKAN meldet das nicht als Fehler, sondern
# antwortet mit `count: 0`. `env_bafu_datasets` fand deshalb nie etwas und
# `env_nabel_current` zeigte nie den Datensatz-Block. Diese Tests nageln den
# geprüften Slug fest — er ist die einzige Stelle, an der ein Tippfehler
# folgenlos aussieht und trotzdem alles abschneidet.


def test_bafu_org_slug_is_the_ckan_name():
    assert api.OPENDATA_BAFU_ORG == "bundesamt-fur-umwelt-bafu"
    assert api.OPENDATA_BAFU_URL.endswith("/organization/bundesamt-fur-umwelt-bafu")


@respx.mock
async def test_dataset_search_filters_on_the_real_org():
    route = respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(200, json={"result": {"count": 0, "results": []}})
    )
    await api.search_bafu_datasets(query="luft")
    assert route.calls.last.request.url.params["fq"] == "organization:bundesamt-fur-umwelt-bafu"


@respx.mock
async def test_nabel_lookup_filters_on_the_real_org():
    route = respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(200, json={"result": {"count": 0, "results": []}})
    )
    await api.fetch_nabel_data("ZUE", parameter="NO2")
    assert route.calls.last.request.url.params["fq"] == "organization:bundesamt-fur-umwelt-bafu"


def test_no_dead_bafu_portal_link_left():
    """Der Portal-Link wird aus demselben Slug gebaut — `/organization/bafu` ist tot."""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "swiss_environment_mcp"
    stale = [
        f"{path.name}:{i}"
        for path in src.rglob("*.py")
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "opendata.swiss/de/organization/bafu" in line
    ]
    assert not stale, f"Toter Portal-Link (Organisation 'bafu' existiert nicht): {stale}"


# --- Nicht angewendeter Kantonsfilter (env_flood_warnings) -------------------
#
# LINDAS führt keinen Kantons-Code, der Filter wird also nicht angewendet. Anders
# als bei `env_hydro_stations` sind die gezeigten Daten echt — nur umfassen sie
# die ganze Schweiz. Der Fehler lag darin, dass die Antwort das nicht deutlich
# genug sagte: im Markdown als Klammerzusatz am Zeilenende, im JSON gar nicht,
# sobald es keine Warnungen gab. Genau dort ist der Hinweis am wichtigsten —
# «keine Warnungen» plus gesetzter Kanton liest sich sonst als kantonale
# Entwarnung.


def test_flood_canton_field_says_it_is_not_applied():
    """MCP-Clients lesen das Input-Schema, nicht den Docstring."""
    field = FloodWarningsInput.model_fields["canton"]
    assert "NICHT ANGEWENDET" in field.description
    assert "ganze Schweiz" in field.description


@respx.mock
async def test_flood_no_warnings_still_says_canton_was_ignored():
    """Der gefährlichste Fall: leere Antwort auf eine kantonale Frage."""
    respx.get(_LINDAS_URL).mock(return_value=httpx.Response(200, json=_sparql_bindings([])))
    out = await env_flood_warnings(FloodWarningsInput(min_level=2, canton="ZH"))
    assert "Keine aktiven Hochwasserwarnungen" in out
    assert "NICHT angewendet" in out
    assert "ganze Schweiz" in out


@respx.mock
async def test_flood_no_warnings_envelope_keeps_the_hint():
    """Im JSON fiel der Hinweis bei leerem Resultat komplett weg."""
    respx.get(_LINDAS_URL).mock(return_value=httpx.Response(200, json=_sparql_bindings([])))
    env = json.loads(
        await env_flood_warnings(
            FloodWarningsInput(min_level=2, canton="ZH", response_format=ResponseFormat.JSON)
        )
    )
    assert env["count"] == 0 and env["match_type"] == "none"
    assert "Keine aktiven Warnungen" in env["note"]
    assert "NICHT angewendet" in env["note"]


@respx.mock
async def test_flood_unapplied_filter_is_not_an_exact_match():
    """`match_type` ist die maschinenlesbare Fassung derselben Aussage.

    Kommt die Antwort ungefiltert zurück, obwohl ein Filter gesetzt war, wäre
    «exact» eine falsche Zusage an jeden Client, der darauf vertraut.
    """
    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [{"id": "2099", "name": "Zürich", "water": "Limmat", "danger": "3"}]
            ),
        )
    )
    with_filter = json.loads(
        await env_flood_warnings(
            FloodWarningsInput(min_level=2, canton="ZH", response_format=ResponseFormat.JSON)
        )
    )
    without = json.loads(
        await env_flood_warnings(
            FloodWarningsInput(min_level=2, response_format=ResponseFormat.JSON)
        )
    )
    assert with_filter["match_type"] == "fuzzy"
    assert without["match_type"] == "exact"
    # Dieselben Daten — nur die Zusage über ihre Passgenauigkeit unterscheidet sich.
    assert with_filter["results"] == without["results"]


@respx.mock
async def test_flood_active_warnings_lead_with_the_hint():
    respx.get(_LINDAS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_sparql_bindings(
                [{"id": "2099", "name": "Zürich", "water": "Limmat", "danger": "3"}]
            ),
        )
    )
    out = await env_flood_warnings(FloodWarningsInput(min_level=2, canton="BE"))
    # Vor der Tabelle, nicht als Fussnote dahinter.
    assert out.index("NICHT angewendet") < out.index("| Station |")
