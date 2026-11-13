"""Retry auf dem CKAN-Pfad (opendata.swiss).

Anlass: der nächtliche Lauf vom 11.11.2026. Beim Einordnen fiel auf, dass
`opendata.swiss` als einzige Quelle neben waldbrandgefahr.ch ganz ohne
Wiederholung abgefragt wurde — ein einzelnes 502 wurde zur Fehlermeldung des
Tools.

Jede Zusicherung hier hat eine Gegenprobe, die im PR steht: Staffel auf einen
Versuch gekürzt, Statusfilter entfernt, Timeout in die Wiederholung
aufgenommen, Budget-Prüfung entfernt — jeweils fallen genau die zugehörigen
Tests.
"""

import os
import sys

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp import api_client as api  # noqa: E402
from swiss_environment_mcp import sparql_client  # noqa: E402

SEARCH = f"{api.OPENDATA_SWISS_API}/package_search"
SHOW = f"{api.OPENDATA_SWISS_API}/package_show"
OK = {"success": True, "result": {"count": 0, "results": []}}


@pytest.fixture(autouse=True)
def _mock_transport(monkeypatch):
    """DNS-Pinning aus (respx), Wartezeiten aufzeichnen statt absitzen.

    Gepatcht wird der Modul-Alias `api._sleep`, nicht `asyncio.sleep` — das
    träfe das stdlib-Modul und damit jeden anderen Test im Prozess.
    """
    waits: list[float] = []

    async def _record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(api, "dns_pin_enabled", False)
    monkeypatch.setattr(api, "_sleep", _record)
    return waits


@respx.mock
async def test_ein_502_wird_wiederholt_und_der_zweite_versuch_zaehlt(_mock_transport):
    route = respx.get(SEARCH).mock(side_effect=[httpx.Response(502), httpx.Response(200, json=OK)])

    assert await api.search_bafu_datasets("Luft") == OK
    assert route.call_count == 2
    assert len(_mock_transport) == 1


@pytest.mark.parametrize("status", sorted(sparql_client.RETRYABLE_STATUS))
@respx.mock
async def test_jeder_transiente_status_wird_wiederholt(status):
    route = respx.get(SHOW).mock(side_effect=[httpx.Response(status), httpx.Response(200, json=OK)])

    assert await api.get_bafu_dataset("x") == OK
    assert route.call_count == 2


@respx.mock
async def test_verbindungsabbruch_wird_wiederholt():
    route = respx.get(SHOW).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json=OK)]
    )

    assert await api.fetch_nabel_stations() == OK
    assert route.call_count == 2


@respx.mock
async def test_nach_der_staffel_faellt_der_letzte_fehler_unveraendert_heraus(_mock_transport):
    """Der Typ bleibt `HTTPStatusError` — `handle_http_error` kennt ihn."""
    route = respx.get(SEARCH).mock(return_value=httpx.Response(502))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await api.fetch_nabel_data("ZUE")

    assert exc.value.response.status_code == 502
    assert route.call_count == api.CKAN_RETRY_MAX_ATTEMPTS
    # Zwischen N Versuchen liegen N-1 Wartezeiten; nach dem letzten keine.
    assert len(_mock_transport) == api.CKAN_RETRY_MAX_ATTEMPTS - 1
    assert "HTTP 502" in api.handle_http_error(exc.value)


@pytest.mark.parametrize("status", [400, 403, 404, 500])
@respx.mock
async def test_eine_deterministische_absage_wird_nicht_wiederholt(status, _mock_transport):
    """4xx ist eine Antwort, kein Aussetzer (CLAUDE.md: «Ein 4xx ist kein Nein»).

    500 steht bewusst dabei: Es ist nicht in `RETRYABLE_STATUS`, und diese
    Liste gilt hier unverändert — eine Politik, nicht zwei.
    """
    route = respx.get(SEARCH).mock(return_value=httpx.Response(status))

    with pytest.raises(httpx.HTTPStatusError):
        await api.search_bafu_datasets("Luft")

    assert route.call_count == 1
    assert _mock_transport == []


@respx.mock
async def test_ein_timeout_wird_nicht_wiederholt(_mock_transport):
    """Ein Versuch, der 15 s hing, lässt im Budget keinen zweiten zu."""
    route = respx.get(SEARCH).mock(side_effect=httpx.ReadTimeout("hängt"))

    with pytest.raises(httpx.ReadTimeout):
        await api.search_bafu_datasets("Luft")

    assert route.call_count == 1
    assert _mock_transport == []


@respx.mock
async def test_html_statt_json_wird_nicht_wiederholt(_mock_transport):
    """Der Fall vom 11.11.2026 — ausdrücklich nicht abgedeckt, und so festgehalten."""
    route = respx.get(SEARCH).mock(
        return_value=httpx.Response(
            200, text="<!DOCTYPE html>", headers={"content-type": "text/html"}
        )
    )

    with pytest.raises(api.UpstreamContractError):
        await api.search_bafu_datasets("Luft")

    assert route.call_count == 1
    assert _mock_transport == []


@respx.mock
async def test_eine_wartezeit_ueber_das_budget_hinaus_wird_nicht_angetreten(
    monkeypatch, _mock_transport
):
    """`Retry-After: 20` liegt innerhalb des Deckels, aber über dem Restbudget."""
    monkeypatch.setattr(api, "CKAN_TOTAL_BUDGET_S", 5.0)
    route = respx.get(SEARCH).mock(return_value=httpx.Response(503, headers={"Retry-After": "20"}))

    with pytest.raises(httpx.HTTPStatusError):
        await api.search_bafu_datasets("Luft")

    assert route.call_count == 1
    assert _mock_transport == []


def test_das_budget_liegt_unter_dem_mcp_client_default():
    """30 s ist `MCP_DEFAULT_TIMEOUT` des Python-SDK; darüber gibt der Aufrufer auf."""
    assert api.CKAN_TOTAL_BUDGET_S < 30.0


@respx.mock
async def test_waldbrand_laeuft_weiter_ohne_wiederholung():
    """Abgrenzung: Dieser PR betrifft nur opendata.swiss."""
    route = respx.get(f"{api.WALDBRAND_BASE}/").mock(return_value=httpx.Response(502))

    with pytest.raises(httpx.HTTPStatusError):
        await api.fetch_wildfire_danger()

    assert route.call_count == 1
