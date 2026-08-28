"""Was passiert, wenn die Quelle antwortet — aber nicht mit JSON?

DER LAUF, DER DIESE DATEI AUSGELÖST HAT
---------------------------------------
Nächtliche Live-Suite vom 23.8.2026, 04:33 UTC: zwei von 23 Tests rot,
`test_nabel_current` und `test_bafu_datasets`. Beide hingen an derselben
Stelle — `opendata.swiss/api/3/action/package_search` lieferte einen Body,
der kein JSON war. Im Log stand:

    JSONDecodeError: Expecting value: line 1 column 1 (char 0)

und im Tool-Ergebnis, das ein Mensch oder ein LLM zu sehen bekam:

    ⚠️ Datensatzsuche fehlgeschlagen: Fehler: Unerwarteter interner Fehler.

Das ist die falsche Aussage. Der Fehler war nicht intern; die Quelle hatte den
Vertrag gebrochen. CLAUDE.md verlangt bei rotem Live-Test «erst die Quelle
abfragen, dann einordnen» — genau diese Meldung verhindert das Einordnen: Sie
zeigt auf uns und nennt weder Status noch Content-Type, an denen der
Unterschied hinge.

Ursache war ein nacktes `response.json()` an fünf Aufrufstellen. `ValueError`
ist keiner der Typen, die `handle_http_error` kennt, also fiel alles in den
Sammelzweig am Ende.

WAS HIER GEPRÜFT WIRD
---------------------
Drei Zusicherungen, jede mit Gegenprobe (CLAUDE.md: eine Zusicherung, die grün
bleibt, wenn man ihre Implementierung entfernt, prüft nichts):

1. `_json_body` wirft `UpstreamContractError` statt `ValueError`.
   Gegenprobe: `test_gegenprobe_nacktes_json_faellt_in_den_sammelzweig` baut den
   alten Pfad (`response.json()`) nach und zeigt, dass er auf genau die
   nichtssagende Meldung führt.
2. `handle_http_error` bildet den neuen Typ auf eine Meldung ab, die die Quelle
   benennt. Gegenprobe: derselbe Test wie oben — ohne den Zweig kommt
   «Unerwarteter interner Fehler» heraus.
3. Ein 3xx bekommt in `handle_http_error` eine eigene Meldung, statt im
   generischen «API-Anfrage fehlgeschlagen» zu verschwinden. Gegenprobe:
   `test_handle_http_error_trennt_redirect_von_anfragefehler` fällt, wenn man
   den Zweig entfernt (gemessen).

Eine vierte Zusicherung wurde durch ihre eigene Gegenprobe wieder entfernt —
siehe den Kommentar bei den Redirect-Tests.

Der Weg über das echte Tool (`test_tool_meldet_quelle_statt_interner_fehler`)
ist der eigentliche Punkt: Er prüft den Text, den ein Aufrufer sieht, nicht nur
den Exception-Typ dazwischen.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from swiss_environment_mcp import api_client as api
from swiss_environment_mcp.server import BafuDatasetsInput, env_bafu_datasets

pytestmark = pytest.mark.anyio

_CKAN = "https://opendata.swiss/api/3/action/package_search"

# Die HTML-Fehlerseite, wie eine Quelle sie hinter einem Reverse-Proxy mit
# einem 200 ausliefert. Der Body ist der Punkt, nicht der genaue Text.
_HTML_BODY = "<html><head><title>503 Service Unavailable</title></head><body>...</body></html>"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _reset_client():
    """Frischer Client je Test; DNS-Pinning aus, damit respx greift (SEC-005)."""
    api.dns_pin_enabled = False
    await api.shutdown()
    yield
    await api.shutdown()
    api.dns_pin_enabled = True


def _response(
    status: int = 200, text: str = _HTML_BODY, content_type: str = "text/html"
) -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("GET", _CKAN),
    )


# --- 1. Der Parser benennt den gebrochenen Vertrag -----------------------------


def test_json_body_wirft_upstream_contract_error_statt_valueerror():
    with pytest.raises(api.UpstreamContractError) as exc:
        api._json_body(_response())

    assert exc.value.status_code == 200
    assert exc.value.content_type == "text/html"
    # Der Auszug macht eine HTML-Fehlerseite von einem leeren Body
    # unterscheidbar — genau die Frage, die am 23.8. offenblieb.
    assert "503 Service Unavailable" in exc.value.excerpt


def test_json_body_erkennt_auch_den_leeren_body():
    """«Expecting value: line 1 column 1» kommt auch von einer Antwort ohne Inhalt.

    Ein leerer Body und eine HTML-Seite sind zwei verschiedene Störungen der
    Quelle. Der alte Pfad warf für beide dieselbe Exception mit derselben
    Meldung; hier trennt sie der Auszug.
    """
    with pytest.raises(api.UpstreamContractError) as exc:
        api._json_body(_response(text="", content_type=""))

    assert exc.value.excerpt == ""
    assert exc.value.content_type == ""


def test_json_body_laesst_gueltiges_json_durch():
    """Die Gegenrichtung: der Guard darf den Normalfall nicht abwürgen."""
    ok = httpx.Response(
        200,
        json={"success": True, "result": {"count": 375}},
        request=httpx.Request("GET", _CKAN),
    )
    assert api._json_body(ok)["result"]["count"] == 375


# --- 2. Die Fehlerabbildung zeigt auf die Quelle ------------------------------


def test_handle_http_error_benennt_die_quelle():
    msg = api.handle_http_error(api.UpstreamContractError(_CKAN, 200, "text/html", "<html>"))

    assert "HTTP 200" in msg
    assert "text/html" in msg
    assert "Datenquelle" in msg
    # Der Kern: nicht mehr die Meldung, die auf uns zeigt.
    assert "Unerwarteter interner Fehler" not in msg


def test_handle_http_error_leakt_keine_interna():
    """OBS-002 bleibt gewahrt: Status und Content-Type stammen von der Quelle.

    Der Exception-Text selbst (mit URL und Body-Auszug) darf nicht in die
    LLM-sichtbare Meldung wandern.
    """
    msg = api.handle_http_error(
        api.UpstreamContractError(_CKAN, 200, "text/html", "<html>geheim-xyz</html>")
    )
    assert "geheim-xyz" not in msg
    assert "Traceback" not in msg


def test_gegenprobe_nacktes_json_faellt_in_den_sammelzweig():
    """Ohne den neuen Typ kommt exakt die Meldung vom 23.8. heraus.

    Das ist die Gegenprobe zu den beiden Tests darüber: Sie baut den alten Pfad
    nach — `response.json()` roh, Ergebnis durch `handle_http_error`. Fiele der
    `UpstreamContractError`-Zweig weg, wäre das wieder das Verhalten, und die
    Zusicherungen oben fielen.
    """
    try:
        _response().json()
    except ValueError as e:
        assert (
            api.handle_http_error(e)
            == "Fehler: Unerwarteter interner Fehler. Bitte erneut versuchen."
        )
    else:  # pragma: no cover - json() muss auf HTML scheitern
        pytest.fail("HTML-Body wurde als JSON geparst")


# --- 3. Ein 3xx ist ein Vertragswechsel, kein Erfolg --------------------------


# Hier stand ein `test_get_json_weist_redirect_ab`, das eine explizite
# `is_redirect`-Prüfung in `_get_json` absichern sollte. Die Gegenprobe hat sie
# als tote Zeile entlarvt: `raise_for_status()` wirft auf 3xx bereits — gemessen
# an httpx 0.27.0 und 0.28.1, den beiden Rändern unseres `httpx>=0.27.0`. Der
# Test blieb grün, wenn man die Prüfung entfernte, belegte also nichts. Prüfung
# und Test sind deshalb beide weg; geblieben ist die Zusicherung darunter, die
# tatsächlich fällt, wenn man ihren Zweig herausnimmt.


def test_handle_http_error_trennt_redirect_von_anfragefehler():
    resp = httpx.Response(302, request=httpx.Request("GET", _CKAN))
    msg = api.handle_http_error(
        httpx.HTTPStatusError("redirect", request=resp.request, response=resp)
    )

    assert "leitet weiter" in msg
    # Gegenprobe zur Abgrenzung: ohne den 3xx-Zweig landete das im generischen
    # Zweig darunter, der jeden Status gleich benennt.
    assert "API-Anfrage fehlgeschlagen" not in msg


def test_weiterleitungsseite_ist_kein_json():
    """Der Body einer Weiterleitung ist Text — auch er darf nicht still durchgehen.

    Gemessen am 28.8.2026: `opendata.swiss/api/3/action/*` beantwortet
    Browser-User-Agents mit 302 auf `ckan.opendata.swiss` und unseren
    User-Agent mit 200. Der Weiterleitungspfad ist also aktiv, nicht
    hypothetisch — er hängt nur daran, wie die Quelle uns einordnet.
    """
    redirect = httpx.Response(
        302,
        text="Found. Redirecting to https://ckan.opendata.swiss/api/3/action/package_search",
        headers={"location": "https://ckan.opendata.swiss/api/3/action/package_search"},
        request=httpx.Request("GET", _CKAN),
    )
    with pytest.raises(api.UpstreamContractError):
        api._json_body(redirect)


# --- 4. Der Weg, den ein Aufrufer tatsächlich sieht ---------------------------


@respx.mock
async def test_tool_meldet_quelle_statt_interner_fehler():
    """Der Live-Fall vom 23.8., End-to-End durch das echte Tool.

    Damals: «⚠️ Datensatzsuche fehlgeschlagen: Fehler: Unerwarteter interner
    Fehler.» Jetzt muss dort stehen, was die Quelle geliefert hat.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    respx.get(_CKAN).mock(return_value=_response())

    with pytest.raises(ToolError) as exc:
        await env_bafu_datasets(BafuDatasetsInput(query="Luftqualität", rows=5))

    text = str(exc.value)
    assert "Unerwarteter interner Fehler" not in text
    assert "HTTP 200" in text and "text/html" in text
    # Die Direktlinks bleiben erhalten — der Aufrufer soll weiterkommen.
    assert "opendata.swiss" in text


# --- 5. Der zweite Pfad: durch die vendored copy ------------------------------
#
# `_get_json_retry` (SLF-Schnee, Lawinenbulletin, Jagdstatistik) läuft nicht
# über `_json_body`, sondern über `sparql_client.get_json`. Der wirft seit
# v1.2.0 der vendored copy `NotJsonError` — den Basistyp, nicht
# `UpstreamContractError`. Prüfte `handle_http_error` auf die Unterklasse,
# stünde dieser halbe Server weiter bei «Unerwarteter interner Fehler».


def test_upstream_contract_error_ist_ein_notjsonerror():
    """Die Vererbung ist der Grund, warum eine Prüfung für beide Pfade reicht."""
    from swiss_environment_mcp import sparql_client

    assert issubclass(api.UpstreamContractError, sparql_client.NotJsonError)


def test_handle_http_error_faengt_auch_den_retry_pfad():
    """Der Basistyp aus der vendored copy bekommt dieselbe Meldung."""
    from swiss_environment_mcp import sparql_client

    msg = api.handle_http_error(sparql_client.NotJsonError(_CKAN, 200, "text/html", "<html>"))

    assert "HTTP 200" in msg and "text/html" in msg
    assert "Unerwarteter interner Fehler" not in msg


@respx.mock
async def test_slf_pfad_meldet_quelle_statt_interner_fehler(monkeypatch):
    """End-to-End über den Retry-Pfad, mit einer echten SLF-URL.

    Ohne Backoff, sonst wartet der Test die Retry-Staffel ab. Genullt wird die
    Modul-Konstante, nicht `asyncio.sleep` — Letzteres entschärfte die Mechanik
    im ganzen Prozess.
    """
    monkeypatch.setattr(api, "RETRY_BASE_DELAY", 0)
    url = f"{api.SLF_MEASUREMENT_API}/imis/stations"
    respx.get(url).mock(
        return_value=httpx.Response(200, text=_HTML_BODY, headers={"content-type": "text/html"})
    )
    with pytest.raises(api.sparql_client.NotJsonError):
        await api.fetch_slf_snow_stations()
