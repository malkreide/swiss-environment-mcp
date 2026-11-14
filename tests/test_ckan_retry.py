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

import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conftest import _source_gap_cause  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from test_integration import _tool_text  # noqa: E402

from swiss_environment_mcp import api_client as api  # noqa: E402
from swiss_environment_mcp import sparql_client  # noqa: E402
from swiss_environment_mcp.server import (  # noqa: E402
    BafuDatasetDetailInput,
    env_bafu_dataset_detail,
)

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


# --- HTML statt JSON (23.8. und 11.11.2026) -----------------------------------
#
# opendata.swiss antwortete mit HTTP 200 und einer HTML-Seite. Beide Male war
# es am Folgetag ohne Codeänderung vorbei. Der Abruf wird deshalb wiederholt;
# hält der Zustand an, fällt ein eigener Typ heraus, den der Live-Lauf als
# Störung der Quelle einordnet statt als Vertragsbruch.

_HTML = httpx.Response(200, text="<!DOCTYPE html>", headers={"content-type": "text/html"})


@respx.mock
async def test_html_statt_json_wird_wiederholt_und_der_zweite_versuch_zaehlt(_mock_transport):
    route = respx.get(SEARCH).mock(side_effect=[_HTML, httpx.Response(200, json=OK)])

    assert await api.search_bafu_datasets("Luft") == OK
    assert route.call_count == 2
    assert len(_mock_transport) == 1


@respx.mock
async def test_anhaltendes_html_endet_als_ckan_not_json_error(_mock_transport):
    route = respx.get(SEARCH).mock(return_value=_HTML)

    with pytest.raises(api.CkanNotJsonError) as exc:
        await api.search_bafu_datasets("Luft")

    assert route.call_count == api.CKAN_RETRY_MAX_ATTEMPTS
    # Die Tatsachen der Quelle bleiben dran; die Meldung zeigt weiter auf sie.
    assert exc.value.status_code == 200 and exc.value.content_type == "text/html"
    msg = api.handle_http_error(exc.value)
    assert "HTTP 200" in msg and "text/html" in msg
    assert "Unerwarteter interner Fehler" not in msg


@pytest.mark.parametrize(
    "aufruf",
    [
        lambda: api.search_bafu_datasets("Luft"),
        lambda: api.get_bafu_dataset("x"),
        lambda: api.fetch_nabel_stations(),
        lambda: api.fetch_nabel_data("ZUE"),
    ],
    ids=["search", "show", "nabel_stations", "nabel_data"],
)
@respx.mock
async def test_alle_vier_ckan_aufrufer_werfen_den_eigenen_typ(aufruf):
    """Sonst liefe einer am Parsen in der Schleife vorbei."""
    respx.get(url__startswith=api.OPENDATA_SWISS_API).mock(return_value=_HTML)

    with pytest.raises(api.CkanNotJsonError):
        await aufruf()


@respx.mock
async def test_ein_anderer_fehler_wird_nicht_umetikettiert(_mock_transport):
    """Nur «2xx ohne JSON» wird zu `CkanNotJsonError` — ein 502 bleibt ein 502."""
    respx.get(SEARCH).mock(return_value=httpx.Response(502))

    with pytest.raises(httpx.HTTPStatusError):
        await api.search_bafu_datasets("Luft")


@respx.mock
async def test_html_von_einer_anderen_quelle_bleibt_ein_vertragsbruch(monkeypatch):
    """Die Sonderbehandlung gilt opendata.swiss, nicht «2xx ohne JSON» überhaupt.

    Bei der Jagdstatistik wäre HTML statt JSON genau die Änderung, die im
    Live-Lauf als Befund auffallen muss.
    """
    monkeypatch.setattr(api, "RETRY_BASE_DELAY", 0)
    respx.get(api.JAGD_STATISTICS_URL).mock(return_value=_HTML)

    with pytest.raises(api.sparql_client.NotJsonError) as exc:
        await api._get_json_retry(api.JAGD_STATISTICS_URL, headers=api.JAGD_AJAX_HEADERS)

    assert not isinstance(exc.value, api.CkanNotJsonError)
    assert _source_gap_cause(exc.value) is None


# --- Der versteckte Status (gemessen am 14.11.2026) ---------------------------
#
# opendata.swiss verpackt jeden Fehler der CKAN-API in eine HTML-Seite mit
# HTTP 200; der Status steht nur im Seitentitel. Die drei Seiten unter
# `tests/recorded_errors/` sind aufgezeichnet, nicht geschrieben.

_AUFGEZEICHNET = Path(__file__).resolve().parent / "recorded_errors"


def _seite(name: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=(_AUFGEZEICHNET / name).read_bytes(),
        headers={"content-type": "text/html; charset=utf-8"},
    )


@pytest.mark.parametrize(
    ("datei", "status"),
    [
        ("ckan_package_show_404_de.html", 404),
        ("ckan_package_show_404_fr.html", 404),  # «Erreur 404» — am Wort hängt nichts
        ("ckan_package_show_409_de.html", 409),
    ],
)
@respx.mock
async def test_die_aufgezeichnete_fehlerseite_gibt_ihren_status_preis(
    datei, status, _mock_transport
):
    route = respx.get(SHOW).mock(return_value=_seite(datei))

    with pytest.raises(api.CkanMaskedStatusError) as exc:
        await api.get_bafu_dataset("gibts-nicht-xyzabc")

    assert exc.value.response.status_code == status
    assert exc.value.transport_status == 200
    # Eine deterministische Absage wird nicht wiederholt.
    assert route.call_count == 1
    assert _mock_transport == []


@respx.mock
async def test_das_werkzeug_meldet_nicht_gefunden_statt_spaeter_erneut(_mock_transport):
    """Der Text, den ein Aufrufer sieht — vorher ein Wiederholungsrat für ein 404."""
    respx.get(SHOW).mock(return_value=_seite("ckan_package_show_404_de.html"))

    with pytest.raises(ToolError) as exc:
        await env_bafu_dataset_detail(BafuDatasetDetailInput(dataset_id="gibts-nicht-xyzabc"))

    text = str(exc.value)
    assert "Ressource nicht gefunden" in text
    assert "später erneut versuchen" not in text
    assert "kein JSON" not in text
    assert "env_bafu_datasets" in text


def test_ein_verstecktes_404_bleibt_im_live_lauf_ein_befund():
    """Fehlt der Anker-Datensatz, hat die Quelle geantwortet: `finding`, kein `unknown`."""
    with respx.mock:
        respx.get(SHOW).mock(return_value=_seite("ckan_package_show_404_de.html"))
        with pytest.raises(api.CkanMaskedStatusError) as exc:
            asyncio.run(api.get_bafu_dataset("x"))

    assert _source_gap_cause(exc.value) is None


# Handgeschrieben: Eine 5xx-Seite lässt sich nicht auf Zuruf auslösen. Dass sie
# dieselbe Form hat wie die aufgezeichneten 4xx-Seiten, ist eine Annahme.
def _seite_5xx(status: int) -> httpx.Response:
    return httpx.Response(
        200,
        text=f'<!DOCTYPE html>\n<html lang="de">\n<head>\n<title>\n  Fehler {status} | \n</title>',
        headers={"content-type": "text/html; charset=utf-8"},
    )


@respx.mock
async def test_ein_verstecktes_503_wird_wiederholt_und_der_zweite_versuch_zaehlt(_mock_transport):
    route = respx.get(SEARCH).mock(side_effect=[_seite_5xx(503), httpx.Response(200, json=OK)])

    assert await api.search_bafu_datasets("Luft") == OK
    assert route.call_count == 2


@respx.mock
async def test_ein_anhaltendes_verstecktes_503_ist_im_live_lauf_eine_stoerung(_mock_transport):
    route = respx.get(SEARCH).mock(return_value=_seite_5xx(503))

    with pytest.raises(api.CkanMaskedStatusError) as exc:
        await api.search_bafu_datasets("Luft")

    assert route.call_count == api.CKAN_RETRY_MAX_ATTEMPTS
    assert "Dienst vorübergehend nicht verfügbar" in api.handle_http_error(exc.value)
    assert _source_gap_cause(exc.value) is exc.value


@respx.mock
async def test_ein_verstecktes_500_wird_nicht_wiederholt(_mock_transport):
    """500 steht nicht in `RETRYABLE_STATUS` — die Liste gilt auch für den versteckten Status."""
    route = respx.get(SEARCH).mock(return_value=_seite_5xx(500))

    with pytest.raises(api.CkanMaskedStatusError):
        await api.search_bafu_datasets("Luft")

    assert route.call_count == 1


@respx.mock
async def test_json_das_wie_eine_fehlerseite_aussieht_bleibt_json():
    """Ein Datensatz darf «<title> Fehler 404» im Text tragen."""
    body = {"success": True, "result": {"notes": "<title> Fehler 404 | </title>"}}
    respx.get(SHOW).mock(return_value=httpx.Response(200, json=body))

    assert await api.get_bafu_dataset("x") == body


@respx.mock
async def test_ein_echtes_404_ueber_die_leitung_ist_kein_versteckter_status():
    respx.get(SHOW).mock(return_value=httpx.Response(404, text="nope"))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await api.get_bafu_dataset("x")

    assert not isinstance(exc.value, api.CkanMaskedStatusError)


# --- Einordnung im Live-Lauf --------------------------------------------------


def _ckan_fehler() -> api.CkanNotJsonError:
    return api.CkanNotJsonError(SEARCH, 200, "text/html", "<!DOCTYPE html>")


def test_der_live_hook_erkennt_die_stoerung_auch_im_toolerror_verpackt():
    """So kommt sie aus `env_bafu_datasets`: als `ToolError` mit `__context__`."""
    try:
        try:
            raise _ckan_fehler()
        except api.CkanNotJsonError:
            raise ToolError("⚠️ Datensatzsuche fehlgeschlagen")  # noqa: B904
    except ToolError as outer:
        assert isinstance(_source_gap_cause(outer), api.CkanNotJsonError)


def test_ein_gewoehnlicher_vertragsbruch_bleibt_ein_befund():
    exc = api.UpstreamContractError(SEARCH, 200, "text/html", "<html>")

    assert _source_gap_cause(exc) is None
    assert _source_gap_cause(AssertionError("Schema kaputt")) is None


async def test_tool_text_reicht_die_stoerung_durch_statt_sie_zu_schlucken():
    """Sonst scheitert der Live-Test an einer Zusicherung über den Fehlertext,

    und der Hook sieht einen `AssertionError` — so wurde der 11.11. zum Befund.
    """

    async def _tool():
        try:
            raise _ckan_fehler()
        except api.CkanNotJsonError:
            raise ToolError("⚠️ Datensatzsuche fehlgeschlagen")  # noqa: B904

    with pytest.raises(ToolError):
        await _tool_text(_tool())


async def test_tool_text_liefert_einen_gewoehnlichen_toolerror_weiter_als_text():
    """Gegenstück: Die Graceful-Degradation der übrigen Tools bleibt."""

    async def _tool():
        raise ToolError("Ressource nicht gefunden")

    assert await _tool_text(_tool()) == "Ressource nicht gefunden"


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
