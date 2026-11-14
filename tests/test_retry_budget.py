"""Budget und Timeout-Meldung: SLF, Jagdstatistik und geo.admin.ch.

Zwei Schwächen, beim Bau des CKAN-Retrys (PR #141) aufgefallen und dort
ausdrücklich liegen gelassen:

1. Eine hängende Quelle hielt den Aufruf 45 s — das Budget der vendored copy,
   für SPARQL bemessen und länger als der MCP-Client-Default von 30 s.
2. Am Ende fiel der eingebaute `TimeoutError` aus `asyncio.timeout` heraus.
   `handle_http_error` kannte ihn nicht («Unerwarteter interner Fehler»), und
   der Transport-Hook der Live-Tests auch nicht (roter Lauf mit Issue statt
   Skip).

Gemessen wird hier mit der echten Uhr. Eine Fake-Uhr, die nur beim Schlafen
vorrückt, könnte eine Zusicherung über echte Zeit nicht widerlegen (CLAUDE.md).
"""

import asyncio
import os
import sys
import time

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conftest import _describe, _transport_cause  # noqa: E402

from swiss_environment_mcp import api_client as api  # noqa: E402

SLF = f"{api.SLF_MEASUREMENT_API}/imis/stations"

# Die gemockte Quelle hängt so lange; das Budget im Test ist ein Bruchteil davon.
_HANG_S = 2.0
_BUDGET_S = 0.1


@pytest.fixture(autouse=True)
def _mock_transport(monkeypatch):
    monkeypatch.setattr(api, "dns_pin_enabled", False)
    monkeypatch.setattr(api, "RETRY_BASE_DELAY", 0)


async def _haengt(request: httpx.Request) -> httpx.Response:
    await asyncio.sleep(_HANG_S)
    return httpx.Response(200, json=[])


@respx.mock
async def test_eine_haengende_quelle_wird_nach_dem_budget_geschnitten(monkeypatch):
    monkeypatch.setattr(api, "RETRY_TOTAL_BUDGET_S", _BUDGET_S)
    respx.get(SLF).mock(side_effect=_haengt)

    started = time.monotonic()
    with pytest.raises(api.UpstreamTimeoutError):
        await api.fetch_slf_snow_stations()
    elapsed = time.monotonic() - started

    assert elapsed >= _BUDGET_S * 0.9, "zu früh geschnitten — das Budget wurde nicht abgewartet"
    assert elapsed < _HANG_S / 2, f"{elapsed:.2f} s — das Budget hat den Aufruf nicht begrenzt"


@respx.mock
async def test_das_budget_gilt_auch_fuer_die_jagdstatistik(monkeypatch):
    """Zweiter Aufrufer desselben Pfads; er darf nicht am Budget vorbeilaufen."""
    monkeypatch.setattr(api, "RETRY_TOTAL_BUDGET_S", _BUDGET_S)
    respx.get(api.JAGD_STATISTICS_URL).mock(side_effect=_haengt)

    with pytest.raises(api.UpstreamTimeoutError):
        await api._get_json_retry(api.JAGD_STATISTICS_URL, headers=api.JAGD_AJAX_HEADERS)


@respx.mock
async def test_der_timeout_wird_als_timeout_gemeldet(monkeypatch):
    monkeypatch.setattr(api, "RETRY_TOTAL_BUDGET_S", _BUDGET_S)
    respx.get(SLF).mock(side_effect=_haengt)

    with pytest.raises(api.UpstreamTimeoutError) as exc:
        await api.fetch_slf_snow_stations()

    msg = api.handle_http_error(exc.value)
    assert "Timeout" in msg
    assert "Unerwarteter interner Fehler" not in msg


@respx.mock
async def test_der_live_hook_erkennt_den_timeout_und_nennt_den_host(monkeypatch):
    """Sonst öffnet eine hängende Quelle nachts ein Issue statt eines Skips."""
    monkeypatch.setattr(api, "RETRY_TOTAL_BUDGET_S", _BUDGET_S)
    respx.get(SLF).mock(side_effect=_haengt)

    with pytest.raises(api.UpstreamTimeoutError) as exc:
        await api.fetch_slf_snow_stations()

    assert _transport_cause(exc.value) is exc.value
    assert "measurement-api.slf.ch" in _describe(exc.value)


def test_das_budget_liegt_unter_dem_mcp_client_default():
    """30 s ist `MCP_DEFAULT_TIMEOUT` des Python-SDK; darüber gibt der Aufrufer auf."""
    assert api.RETRY_TOTAL_BUDGET_S < 30.0


@respx.mock
async def test_eine_schnelle_antwort_bleibt_unberuehrt():
    respx.get(SLF).mock(return_value=httpx.Response(200, json=[{"code": "X"}]))

    assert await api.fetch_slf_snow_stations() == [{"code": "X"}]


@respx.mock
async def test_ein_httpx_timeout_aus_dem_inneren_geht_unveraendert_durch():
    """`ConnectTimeout` ist kein eingebauter `TimeoutError` — nicht umetikettieren."""
    respx.get(SLF).mock(side_effect=httpx.ConnectTimeout("zu"))

    with pytest.raises(httpx.ConnectTimeout):
        await api.fetch_slf_snow_stations()


@respx.mock
async def test_ein_transienter_status_wird_weiter_wiederholt():
    """Das Budget darf die Wiederholung nicht abschaffen."""
    route = respx.get(SLF).mock(side_effect=[httpx.Response(502), httpx.Response(200, json=[])])

    assert await api.fetch_slf_snow_stations() == []
    assert route.call_count == 2


# --- geo.admin.ch: ein Budget über den ganzen Tool-Aufruf ---------------------
#
# Eine Registerübersicht ohne Filter fragt acht Sublayer nacheinander, eine
# Punktabfrage bis zu zwei Radien. Der Deckel gilt der Summe: Mit dem Budget
# der vendored copy je Abruf (45 s) waren es im schlimmsten Fall 6 Minuten.

IDENTIFY = api.geoadmin.IDENTIFY_URL
# Jeder einzelne Abruf bleibt klar unter dem Budget, erst die Summe sprengt es.
_SLOW_S = 0.1
_GEO_BUDGET_S = 0.35


@pytest.fixture
def _geo(monkeypatch):
    monkeypatch.setattr(api, "GEOADMIN_RETRY_BASE_DELAY", 0)
    monkeypatch.setattr(api, "GEOADMIN_TOTAL_BUDGET_S", _GEO_BUDGET_S)


async def _langsam(request: httpx.Request) -> httpx.Response:
    await asyncio.sleep(_SLOW_S)
    return httpx.Response(200, json={"results": []})


@respx.mock
async def test_das_budget_gilt_der_summe_der_acht_sublayer(_geo):
    """Kein Abruf hängt — und trotzdem ist nach dem Budget Schluss."""
    route = respx.get(IDENTIFY).mock(side_effect=_langsam)
    assert len(api.geoadmin.PERIODS) * _SLOW_S > _GEO_BUDGET_S, "Testaufbau trägt nicht"

    started = time.monotonic()
    with pytest.raises(api.UpstreamTimeoutError):
        await api.fetch_aircraft_noise_registers()
    elapsed = time.monotonic() - started

    assert elapsed < len(api.geoadmin.PERIODS) * _SLOW_S
    assert 1 <= route.call_count < len(api.geoadmin.PERIODS)


@respx.mock
async def test_ein_einzelner_sublayer_passt_ins_budget(_geo):
    """Gegenstück: Das Budget schneidet nicht, was hineinpasst."""
    respx.get(IDENTIFY).mock(side_effect=_langsam)

    assert await api.fetch_aircraft_noise_registers("day") == []


@respx.mock
async def test_die_punktabfrage_wird_nach_dem_budget_geschnitten(_geo):
    respx.get(IDENTIFY).mock(side_effect=_haengt)

    started = time.monotonic()
    with pytest.raises(api.UpstreamTimeoutError) as exc:
        await api.fetch_aircraft_noise("day", 2685000, 1258000)

    assert time.monotonic() - started < _HANG_S / 2
    assert "Timeout" in api.handle_http_error(exc.value)
    assert "api3.geo.admin.ch" in _describe(exc.value)


@respx.mock
async def test_ein_geschnittener_abruf_zaehlt_nicht_als_erfolg(_geo):
    """`last_success` darf nur nach einer echten Antwort vorrücken."""
    api._geoadmin_last_success.pop("night_first", None)
    respx.get(IDENTIFY).mock(side_effect=_haengt)

    with pytest.raises(api.UpstreamTimeoutError):
        await api.fetch_aircraft_noise_registers("night_first")

    assert api.geoadmin_last_success("night_first") is None


def test_das_geoadmin_budget_liegt_unter_dem_mcp_client_default():
    assert api.GEOADMIN_TOTAL_BUDGET_S < 30.0


# --- Das Netz darunter: der eingebaute `TimeoutError` -------------------------
#
# Alle heutigen Aufrufer wandeln ihn in `UpstreamTimeoutError`. Die Einordnung
# bleibt trotzdem, für den nächsten, der `sparql_client` direkt ruft.


def test_der_eingebaute_timeouterror_wird_als_timeout_gemeldet():
    msg = api.handle_http_error(TimeoutError())

    assert "Timeout" in msg
    assert "Unerwarteter interner Fehler" not in msg


def test_der_live_hook_erkennt_den_eingebauten_timeouterror():
    exc = TimeoutError()

    assert _transport_cause(exc) is exc
    assert "TimeoutError" in _describe(exc)
