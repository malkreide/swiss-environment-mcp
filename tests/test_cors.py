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
