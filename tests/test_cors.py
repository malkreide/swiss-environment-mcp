"""SDK-004: Die CORS-Freigabeliste nennt jetzt Header statt einer Wildcard.

`allow_headers` stand auf `["*", "Mcp-Session-Id"]`, und die Wildcard gewann.
Starlette schaltet damit auf `allow_all_headers` und spiegelt im Preflight
zurück, was der Browser ankündigt — jeder erlaubte Origin durfte also jeden
beliebigen Header senden.

Die zu weite Freigabe ist nur die eine Hälfte. Eine Wildcard kann auch nicht
falsch werden: fällt ein Header weg, den das Protokoll braucht, bleibt alles
grün. Deshalb ist die Liste explizit — sie ist prüfbar, die Wildcard nicht.

Geprüft wird mit echten Anfragen gegen die zusammengebaute App, nicht durch
Nachsehen im Middleware-Stack: die Anwesenheit eines `CORSMiddleware`-Objekts
zu behaupten, wäre auch bei leerer Liste grün.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swiss_environment_mcp.server import (
    CORS_ALLOW_HEADERS,
    CORS_ROUTING_HEADERS,
    build_cors_app,
)

ORIGIN = "https://client.example"


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_cors_app(origins=[ORIGIN]))


def preflight(client: TestClient, request_headers: str, method: str = "POST"):
    """Sende einen Preflight.

    `request_headers` ist, was der Browser anzukündigen vorgibt. Das muss auf
    der Anfrage reiten und nicht bloss von der Antwort abgelesen werden:
    Starlette beantwortet einen Preflight, der einen nicht freigegebenen Header
    nennt, mit **400 und ohne `Access-Control-Allow-Origin`**.
    """
    return client.options(
        "/mcp",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": request_headers,
        },
    )


@pytest.mark.parametrize("header", CORS_ALLOW_HEADERS)
def test_jeder_freigegebene_header_passiert_den_preflight(client: TestClient, header: str) -> None:
    """Einzeln parametrisiert: ein Sammelaufruf bliebe grün, wenn nur einer der
    Header freigegeben wäre und Starlette den Rest durchwinkte."""
    resp = preflight(client, header)
    assert resp.status_code == 200, f"Preflight mit {header} abgewiesen"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_die_header_zusammen(client: TestClient) -> None:
    """Was ein Browser tatsächlich schickt: alle auf derselben Anfrage."""
    resp = preflight(client, ", ".join(h.lower() for h in CORS_ALLOW_HEADERS))
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_ein_nicht_freigegebener_header_wird_abgewiesen(client: TestClient) -> None:
    """Die Gegenkontrolle — und der eigentliche Befund.

    Ohne sie wären die Tests darüber gegen die alte Wildcard genauso grün. Sie
    ist die einzige Zusicherung hier, die zwischen «Liste» und «alles erlaubt»
    unterscheidet.
    """
    resp = preflight(client, "x-beliebiger-header")
    assert resp.status_code == 400, "die Freigabeliste winkt weiterhin alles durch"


def test_die_liste_nennt_jeden_routing_header_den_das_sdk_liest() -> None:
    """Gegen die SDK-Konstanten gehalten, nicht gegen abgeschriebenen Spec-Text."""
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    erlaubt = {h.lower() for h in CORS_ALLOW_HEADERS}
    noetig = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert noetig <= erlaubt, f"nicht freigegeben: {sorted(noetig - erlaubt)}"
    assert {h.lower() for h in CORS_ROUTING_HEADERS} == noetig


def test_die_liste_nennt_den_wiederaufnahme_header() -> None:
    """`Last-Event-ID` setzt einen abgerissenen SSE-Strom fort. Fehlt er, bricht
    ausschliesslich die Wiederaufnahme nach Paketverlust — unter Last, in
    Produktion, ohne dass ein Test etwas dazu sagt."""
    from mcp.server.streamable_http import LAST_EVENT_ID_HEADER

    assert LAST_EVENT_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_die_liste_nennt_den_session_header() -> None:
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_keine_wildcard_in_der_freigabeliste() -> None:
    """Die Regression, die dieser Test abfängt, war genau ein Zeichen."""
    assert "*" not in CORS_ALLOW_HEADERS


async def test_kein_werkzeug_deklariert_einen_mcp_param_header() -> None:
    """`Mcp-Param-*` trägt ein Werkzeug-Argument als HTTP-Header, angemeldet
    über eine `x-mcp-header`-Annotation im Eingabeschema. CORS kennt kein
    Präfix-Wildcard, also muss das erste Werkzeug, das einen benutzt, genau
    diesen Header in `CORS_ALLOW_HEADERS` nennen."""
    from swiss_environment_mcp.server import mcp

    treffer = [t.name for t in await mcp.list_tools() if "x-mcp-header" in str(t.input_schema)]
    assert not treffer, (
        f"{treffer} deklarieren einen Mcp-Param-Header — in CORS_ALLOW_HEADERS nennen"
    )


def test_ein_fremder_origin_wird_weiterhin_abgewiesen(client: TestClient) -> None:
    """Die Header-Liste ändert nichts an der Origin-Prüfung."""
    resp = client.options(
        "/mcp",
        headers={
            "Origin": "https://fremd.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


# ── Origins ────────────────────────────────────────────────────────────────
#
# `mcp_cors_allow_origins` stand auf `"*"`. Gemessen am zusammengebauten
# ASGI-Stack bekam ein Preflight von `https://evil.example` dasselbe
# `Access-Control-Allow-Origin: *` wie `https://client.example` — jede Website
# im Netz durfte diesen Server aus dem Browser eines Besuchers aufrufen, und
# niemand hatte das gewählt.
#
# Die Fixture oben reicht `origins=[ORIGIN]` selbst herein und hätte den
# Default deshalb nie widerlegen können. Die Tests hier fassen ihn direkt an.


def test_der_default_laesst_keinen_browser_durch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed am Feld selbst, ohne Umweg über das Singleton.

    Die gelöschte Umgebungsvariable gehört dazu: `Settings` liest sonst eine
    zufällig gesetzte Variable der Testumgebung, und der Test misst etwas
    anderes als den Default.
    """
    from swiss_environment_mcp.server import Settings

    monkeypatch.delenv("MCP_CORS_ALLOW_ORIGINS", raising=False)
    frisch = Settings()
    assert frisch.mcp_cors_allow_origins == ""
    assert frisch.cors_origins() == []


def test_ohne_konfigurierte_origin_kommt_kein_browser_durch() -> None:
    """Und dasselbe durch den ganzen Stack: kein `Access-Control-Allow-Origin`.

    stdio- und Nicht-Browser-Clients sind davon unberührt — CORS regelt
    ausschliesslich Browser.
    """
    c = TestClient(build_cors_app(origins=[]))
    resp = preflight(c, "content-type")
    assert "access-control-allow-origin" not in resp.headers


def test_die_wildcard_bleibt_erreichbar_muss_aber_verlangt_werden() -> None:
    """Einen Default verschärfen ist nicht dasselbe wie die Option streichen.
    Wer Any-Origin will, bekommt es weiterhin — bewusst, und der Server
    protokolliert es."""
    c = TestClient(build_cors_app(origins=["*"]))
    assert preflight(c, "content-type").headers["access-control-allow-origin"] == "*"


def test_eine_wildcard_neben_echten_origins_wird_gemeldet() -> None:
    """Die Warnung prüfte `origins == ["*"]` — exakte Gleichheit.

    `MCP_CORS_ALLOW_ORIGINS="https://a.test,*"` erlaubt bei Starlette ebenso
    jede Origin (`allow_all_origins`), rutschte aber still durch: die Liste war
    ja nicht *gleich* `["*"]`. Genau die Mischform ist die, die man versehentlich
    hinschreibt, wenn man eine Origin ergänzt und die Wildcard stehen lässt.

    Abgegriffen mit `structlog.testing.capture_logs`, nicht mit `caplog` oder
    `capfd`: dieser Server rendert über eine `PrintLoggerFactory` direkt auf
    stderr, am `logging`-Handler vorbei, und `cache_logger_on_first_use` hält
    den Stream von vor dem Test fest. Beide Fixtures blieben leer — der Test
    wäre gefallen, obwohl die Meldung da war.
    """
    import structlog.testing

    with structlog.testing.capture_logs() as logs:
        c = TestClient(build_cors_app(origins=["https://a.test", "*"]))
    assert "cors_wildcard_origin" in [eintrag.get("event") for eintrag in logs]
    # Und die Wirkung, nicht nur die Meldung: die Wildcard gewinnt weiterhin.
    assert preflight(c, "content-type").headers["access-control-allow-origin"] == "*"


def test_der_leere_fall_wird_vermerkt() -> None:
    """Fail-closed ist richtig, aber nicht selbsterklärend: wer einen Browser
    erwartet und keinen bekommt, soll den Grund im Log finden und nicht im
    Quelltext suchen müssen."""
    import structlog.testing

    with structlog.testing.capture_logs() as logs:
        build_cors_app(origins=[])
    assert "cors_no_origins" in [eintrag.get("event") for eintrag in logs]


def test_cors_origins_liest_eine_liste(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kommasepariert, Leerzeichen weg, leere Einträge raus."""
    from swiss_environment_mcp.server import Settings

    monkeypatch.setenv("MCP_CORS_ALLOW_ORIGINS", " https://a.test , ,https://b.test ")
    assert Settings().cors_origins() == ["https://a.test", "https://b.test"]
