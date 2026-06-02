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
    BafuDatasetsInput,
    FloodWarningsInput,
    HydroStationsInput,
    NabelCurrentInput,
    NabelStationsInput,
    ResponseFormat,
    env_air_limits_check,
    env_bafu_datasets,
    env_flood_warnings,
    env_hydro_stations,
    env_nabel_current,
    env_nabel_stations,
    health,
)


@pytest.fixture(autouse=True)
async def _reset_client():
    """Frischen geteilten Client je Test, sauber schliessen (SDK-001)."""
    await api.shutdown()
    yield
    await api.shutdown()


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
    respx.get("https://www.hydrodaten.admin.ch/lhg/az/json/warnings.json").mock(
        return_value=httpx.Response(200, json={"stations": []})
    )
    out = await env_flood_warnings(FloodWarningsInput(min_level=2))
    assert "Keine aktiven Hochwasserwarnungen" in out


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
    """Execution-Error-Pfad: maskiertes Result, ctx.warning, strukturiertes Log (OBS-001)."""
    from structlog.testing import capture_logs

    from swiss_environment_mcp.server import env_bafu_datasets

    respx.get("https://opendata.swiss/api/3/action/package_search").mock(
        return_value=httpx.Response(500)
    )
    ctx = _FakeContext()
    with capture_logs() as logs:
        out = await env_bafu_datasets(BafuDatasetsInput(query="x"), ctx=ctx)
    # User-Result enthält keine Internals, aber den Fallback-Hinweis
    assert "fehlgeschlagen" in out
    assert "Traceback" not in out and "500 Internal" not in out
    # Fehler wurde über den Context gemeldet ...
    assert ctx.warnings and "env_bafu_datasets" in ctx.warnings[0]
    # ... und strukturiert geloggt (Event tool_error mit tool-Feld)
    assert any(
        e.get("event") == "tool_error" and e.get("tool") == "env_bafu_datasets" for e in logs
    )


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
    assert len(tools) == 12
    missing = [t.name for t in tools if "<use_case>" not in (t.description or "")]
    assert not missing, f"Tools ohne <use_case>-Tag: {missing}"


# --- CORS / Mcp-Session-Id (SDK-004) ------------------------------------------


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
