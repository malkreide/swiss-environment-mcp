"""Spec 2026-07-28 am echten Draht — gemessen statt aus Konstanten geschlossen.

`test_protocol_version.py` pinnt die beiden Revisionen gegen die SDK-Konstanten
und sagt dort selbst, dass das die schwaechere Form ist: «dieses Repo baut keine
ASGI-App, durch die sich ein `initialize` schicken liesse». Das stimmte nicht —
`build_cors_app()` ist genau diese App, uvicorn startet sie im Betrieb, und der
ASGI-Lifespan laesst sich ohne uvicorn fahren (:func:`_lifespan`). Diese Datei
schickt deshalb echte Anfragen durch die Produktions-App.

Warum das mehr ist als Doppelung: Die Konstanten-Zusicherung wuerde auch dann
gruen bleiben, wenn dieser Server die moderne Aera gar nicht beantwortete. Sie
misst das SDK, nicht uns. Hier faellt etwas, sobald *dieser* Server die Revision
nicht mehr bedient — und die Negativkontrollen weiter unten zeigen, dass die
Leiter ueberhaupt laeuft, statt jede Anfrage durchzuwinken.

Was Spec 2026-07-28 aendert, und warum es diesen Server betrifft:

* **Kein `initialize`.** Eine Anfrage traegt ihren Umschlag selbst
  (`params._meta`), es gibt keine Sitzung. Damit faellt das Feld weg, in dem
  sich ein Server bisher vorgestellt hat — `serverInfo` des
  `initialize`-Resultats. An seine Stelle treten `server/discover` und der
  `_meta`-Stempel an jedem Resultat. Beide speist dasselbe Konstruktor-Argument.
* **Routing-Header.** `Mcp-Method`, `Mcp-Name` und `MCP-Protocol-Version`
  muessen zum Koerper passen, sonst `-32020`. Das macht die Liste in
  `CORS_ALLOW_HEADERS` lasttragend: Ein Browser, der sie nicht senden darf,
  bekommt keine Antwort, sondern eine Abweisung.
* **Logging wird Opt-in pro Anfrage** (SEP-2577). Die Capability ist weg; ohne
  den reservierten `_meta`-Schluessel `io.modelcontextprotocol/logLevel` DARF
  der Server nichts senden. `_handle_tool_error` — die Fehlerbehandlung aller
  21 Werkzeuge — ruft `ctx.warning`, haengt also an genau diesem Schalter.
  Beide Richtungen stehen unten gemessen.
* **Kein Rueckkanal.** Der Server kann in dieser Aera keine *Anfrage* an den
  Client stellen (`can_send_request=False`). Benachrichtigungen bleiben
  moeglich, sie reiten auf dem SSE-Strom der Antwort.

Beide Aeren teilen sich denselben Endpunkt; welche gilt, entscheidet die erste
Anfrage. Auch das steht hier gemessen, nicht nur in der README.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    LOG_LEVEL_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    SERVER_INFO_META_KEY,
)

from swiss_environment_mcp import __version__
from swiss_environment_mcp import api_client as api
from swiss_environment_mcp.server import (
    SERVER_TITLE,
    SERVER_WEBSITE_URL,
    build_cors_app,
    mcp,
)

# Die Revision, um die es hier geht. Bewusst ein Literal und nicht
# `LATEST_MODERN_VERSION`: gegen die SDK-Konstante zu pruefen hiesse, das SDK
# mit sich selbst zu vergleichen. Dass Literal und Konstante uebereinstimmen,
# sichert `test_protocol_version.py` — diese Datei misst, was auf dem Draht
# passiert, wenn genau diese Revision verlangt wird.
MODERN = "2026-07-28"

# Die Aera, die heutige Clients sprechen. Steht hier, damit der Koexistenz-Test
# unten nicht auf eine SDK-Konstante ausweicht.
HANDSHAKE = "2025-11-25"

# Loopback: `build_transport_security` leitet die Host-Allow-List aus diesem
# Wert ab. Die `base_url` unten muss deshalb dazu passen, sonst antwortet der
# Transport mit 421, bevor irgendeine Protokoll-Logik laeuft.
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"

# Ein Werkzeug ohne Netzwerk: die LSV-Grenzwertpruefung rechnet lokal. Ein
# netzabhaengiges Werkzeug wuerde hier die Fremd-API testen statt den Transport.
LOCAL_TOOL = "env_noise_limits_check"
LOCAL_TOOL_ARGS: dict[str, Any] = {
    "params": {"level_db": 62, "sensitivity_level": "II", "period": "day"}
}


def envelope() -> dict[str, Any]:
    """Der Pro-Request-Umschlag, den Spec 2026-07-28 verlangt.

    `clientInfo` fehlt absichtlich: die Spec fuehrt es als SHOULD, nicht als
    MUST. Es wegzulassen ist damit selbst eine Zusicherung — ein Server, der
    darauf besteht, waere zu streng.
    """
    return {
        PROTOCOL_VERSION_META_KEY: MODERN,
        CLIENT_CAPABILITIES_META_KEY: {},
    }


def modern_headers(method: str, name: str | None = None) -> dict[str, str]:
    """Die Header, nach denen die moderne Aera routet."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MODERN,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def modern_body(method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    body_params: dict[str, Any] = dict(params or {})
    body_params["_meta"] = envelope()
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": body_params}


@asynccontextmanager
async def _lifespan(app: Any) -> AsyncIterator[None]:
    """Faehrt das ASGI-Lifespan-Protokoll, wie uvicorn es faehrt.

    Ohne diesen Schritt wirft der Session-Manager «Task group is not
    initialized» — `httpx.ASGITransport` spricht nur den `http`-Scope an.
    Genau darum stand in der README, es gebe hier keine App, durch die sich
    eine Anfrage schicken liesse: Der erste Versuch scheitert an dieser Stelle
    und sieht wie eine Sackgasse aus.

    Bewusst nacktes `asyncio` statt `anyio.create_task_group()`: Eine
    Task-Gruppe darf das `yield` einer pytest-asyncio-Fixture nicht
    ueberspannen. pytest-asyncio faehrt Auf- und Abbau in verschiedenen Tasks,
    und anyio bricht das mit «Attempted to exit cancel scope in a different
    task than it was entered in» ab — eine Meldung, die nach einem Fehler im
    Test aussieht und keiner ist.
    """
    inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    started = asyncio.Event()
    stopped = asyncio.Event()
    failures: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return await inbox.get()

    async def send(message: dict[str, Any]) -> None:
        if message["type"].endswith(".failed"):
            failures.append(message)
        if message["type"].startswith("lifespan.startup."):
            started.set()
        elif message["type"].startswith("lifespan.shutdown."):
            stopped.set()

    task = asyncio.create_task(app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send))
    inbox.put_nowait({"type": "lifespan.startup"})
    await started.wait()
    assert not failures, f"Lifespan-Start fehlgeschlagen: {failures}"
    try:
        yield
    finally:
        inbox.put_nowait({"type": "lifespan.shutdown"})
        await stopped.wait()
        await task


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Ein HTTP-Client auf der echten Produktions-App.

    `build_cors_app` ist der Pfad, den `main()` im HTTP-Transport nimmt — samt
    CORS-Middleware und Transport-Sicherheit. Eine nackte
    `mcp.streamable_http_app()` waere bequemer und wuerde genau die beiden
    Schichten ueberspringen, die dieses Repo selbst gesetzt hat.
    """
    app = build_cors_app([], HOST, PORT)
    async with _lifespan(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL
        ) as http:
            yield http


async def post_modern(
    client: httpx.AsyncClient,
    method: str,
    params: Mapping[str, Any] | None = None,
    name: str | None = None,
) -> httpx.Response:
    return await client.post(
        "/mcp", json=modern_body(method, params), headers=modern_headers(method, name)
    )


def result_of(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "error" not in payload, payload["error"]
    return payload["result"]


def error_of(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    assert "error" in payload, f"erwartet wurde eine Abweisung, kam: {payload}"
    return payload["error"]


# --- Die Aera antwortet ueberhaupt -------------------------------------------


async def test_server_discover_antwortet_auf_dem_modernen_draht(
    client: httpx.AsyncClient,
) -> None:
    """Die native Entdeckungsmethode der Aera ohne Handshake.

    `server/discover` ersetzt, wofuer frueher `initialize` da war. Antwortet
    sie nicht, ist dieser Server fuer einen zustandslosen Client unsichtbar —
    und keine Konstanten-Zusicherung wuerde das merken.
    """
    result = result_of(await post_modern(client, "server/discover"))

    assert result["supportedVersions"] == [MODERN], result["supportedVersions"]
    assert result["capabilities"]["tools"], "der Server meldet keine Werkzeug-Faehigkeit"
    assert result["instructions"], "ohne `instructions` bekommt ein Client keinen Kontext"


@pytest.mark.parametrize(
    "method",
    ["tools/list", "resources/list", "resources/templates/list", "prompts/list"],
)
async def test_die_auflistenden_methoden_antworten_modern(
    client: httpx.AsyncClient, method: str
) -> None:
    """Jede Verzeichnis-Methode einzeln — ein Sammel-Test wuerde verschweigen,
    welche fehlt."""
    result = result_of(await post_modern(client, method))

    assert result["resultType"] == "complete", result.get("resultType")


async def test_ein_werkzeugaufruf_laeuft_ueber_den_modernen_draht(
    client: httpx.AsyncClient,
) -> None:
    """Der Fall, auf den es ankommt: nicht nur auflisten, sondern rechnen."""
    result = result_of(
        await post_modern(
            client,
            "tools/call",
            {"name": LOCAL_TOOL, "arguments": LOCAL_TOOL_ARGS},
            name=LOCAL_TOOL,
        )
    )

    assert not result.get("isError"), result
    text = result["content"][0]["text"]
    assert "Immissionsgrenzwert" in text, text[:300]


# --- Negativkontrollen: laeuft die Leiter ueberhaupt? -------------------------
#
# Ohne diesen Block koennten die Tests oben auch dann gruen sein, wenn der
# Server jede beliebige Anfrage beantwortete und die Aera gar nicht unterschiede.


async def test_eine_anfrage_ohne_umschlag_wird_abgewiesen(client: httpx.AsyncClient) -> None:
    """Der Umschlag ist das, was die moderne Aera ausmacht. Fehlt er, muss die
    Anfrage fallen — sonst misst `test_die_auflistenden_methoden_antworten_modern`
    nur, dass der Server irgendetwas zurueckgibt."""
    response = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers=modern_headers("tools/list"),
    )

    assert response.status_code == 400, response.text
    assert error_of(response)["code"] == -32602


async def test_ein_falscher_routing_header_wird_abgewiesen(client: httpx.AsyncClient) -> None:
    """Warum `CORS_ALLOW_HEADERS` lasttragend ist, gemessen statt behauptet.

    Der Koerper sagt `tools/list`, der Header `resources/list`. Die Spec
    verlangt dafuer `-32020` (HEADER_MISMATCH). Faellt dieser Test, routet der
    Server nach dem Koerper allein — dann sind die Header in
    `CORS_ROUTING_HEADERS` Dekoration, und ein Browser, dem sie fehlen, merkt
    nichts davon, bis etwas anderes bricht.

    Die andere Haelfte — dass `CORS_ALLOW_HEADERS` diese Header auch wirklich
    freigibt — steht in `test_cors.py`
    (`test_die_liste_nennt_jeden_routing_header_den_das_sdk_liest`) und haengt
    dort an den SDK-Konstanten. Sie hier gegen `CORS_ROUTING_HEADERS` zu
    wiederholen waere eine Tautologie: `CORS_ALLOW_HEADERS` entsteht aus genau
    dieser Liste, der Test koennte also nie fallen. Genau so stand er hier
    einen Commit lang, bis die Gegenprobe ihn entlarvte.
    """
    response = await client.post(
        "/mcp",
        json=modern_body("tools/list"),
        headers=modern_headers("resources/list"),
    )

    assert response.status_code == 400, response.text
    assert error_of(response)["code"] == -32020


# --- Die beiden Aeren nebeneinander ------------------------------------------


async def test_ein_initialize_auf_der_modernen_verbindung_wird_abgewiesen(
    client: httpx.AsyncClient,
) -> None:
    """Die READMEs sagen «ein spaeterer Anspruch der anderen Aera wird
    abgelehnt». Gemessen hat das bisher nichts."""
    response = await client.post(
        "/mcp",
        json=modern_body("initialize", {"protocolVersion": MODERN}),
        headers=modern_headers("initialize"),
    )

    assert response.status_code == 404, response.text
    assert error_of(response)["code"] == -32601


async def test_der_handshake_bleibt_auf_demselben_endpunkt_erreichbar(
    client: httpx.AsyncClient,
) -> None:
    """Der teuerste denkbare Fehler dieser Umstellung: die moderne Aera zu
    bedienen und dabei die Aera zu verlieren, die heutige Clients sprechen.

    Derselbe Endpunkt, dieselbe App, nur ein `initialize` mit
    Handshake-Revision. Die Antwort kommt als SSE-Ereignis, nicht als JSON —
    ein `response.json()` liefe hier ins Leere und sagte nichts ueber die Aera.
    """
    response = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": HANDSHAKE,
                "capabilities": {},
                "clientInfo": {"name": "gate", "version": "0"},
            },
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": HANDSHAKE,
        },
    )

    assert response.status_code == 200, response.text
    payloads = [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert payloads, f"kein SSE-Ereignis in der Antwort: {response.text[:400]!r}"
    result = payloads[0]["result"]
    assert result["protocolVersion"] == HANDSHAKE, result["protocolVersion"]


# --- Identitaet: das einzige, was ein zustandsloser Client zu sehen bekommt ---


async def test_jede_moderne_antwort_nennt_die_release_nummer(
    client: httpx.AsyncClient,
) -> None:
    """Der Befund, der diese Umstellung ausgeloest hat.

    Gemessen vor der Aenderung: `version=''` in jedem `serverInfo`-Stempel —
    der Default von `MCPServer.__init__`. In der Handshake-Aera war das
    laesslich, weil ein Client die Nummer aus dem Registry-Manifest lesen kann.
    In dieser Aera gibt es keine Sitzung und kein `initialize`-Resultat: der
    Stempel IST der Kanal. Ein Client konnte v0.6.0 nicht von v0.4.0
    unterscheiden und damit nicht sagen, ob ein Werkzeug, das er kennt, hier
    noch dasselbe bedeutet.

    Geprueft ueber mehrere Methoden, weil das SDK den Stempel je Resultat setzt
    und nicht einmal je Verbindung.
    """
    for method in ("server/discover", "tools/list", "resources/list"):
        stamp = result_of(await post_modern(client, method))["_meta"][SERVER_INFO_META_KEY]

        assert stamp["version"], f"{method}: `serverInfo.version` ist leer"
        assert stamp["version"] == __version__, f"{method}: {stamp['version']} != {__version__}"
        assert stamp["title"] == SERVER_TITLE, method
        assert stamp["websiteUrl"] == SERVER_WEBSITE_URL, method


async def test_die_identitaet_steht_auch_in_der_handshake_aera(
    client: httpx.AsyncClient,
) -> None:
    """Dieselbe Quelle, beide Aeren — sonst waere die Nummer nur dort richtig,
    wo gerade jemand hingesehen hat."""
    response = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": HANDSHAKE,
                "capabilities": {},
                "clientInfo": {"name": "gate", "version": "0"},
            },
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": HANDSHAKE,
        },
    )

    data = next(
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    assert data["result"]["serverInfo"]["version"] == __version__


# --- Logging: von der Capability zum Opt-in pro Anfrage (SEP-2577) -----------
#
# Spec 2026-07-28 streicht die Logging-*Capability*. Was bleibt, ist ein Opt-in
# pro Anfrage: der Client setzt `io.modelcontextprotocol/logLevel` im
# `_meta`-Umschlag, und ohne diesen Schluessel DARF der Server nichts senden.
#
# Das betrifft hier keinen Randfall, sondern `_handle_tool_error` — die zentrale
# Fehlerbehandlung aller 21 Werkzeuge ruft `ctx.warning`. Die beiden Tests unten
# sind einander Gegenprobe: Der eine zeigt, dass nichts gesendet wird, der
# andere, dass dieselbe Anfrage mit Opt-in sehr wohl etwas liefert. Faende nur
# der erste statt, waere er auch dann gruen, wenn der Kanal gar nicht existierte.


async def _failing_tool_call(client: httpx.AsyncClient, log_level: str | None) -> httpx.Response:
    """Ein echter Upstream-Ausfall, der `_handle_tool_error` durchlaeuft.

    CKAN antwortet 503; gemockt statt live, damit der Test keine Fremd-API
    braucht. `dns_pin_enabled` muss dafuer aus sein — sonst greift der
    Egress-Guard vor respx.
    """
    meta = dict(envelope())
    if log_level is not None:
        meta[LOG_LEVEL_META_KEY] = log_level

    with respx.mock:
        respx.get("https://opendata.swiss/api/3/action/package_search").mock(
            return_value=httpx.Response(503)
        )
        return await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "env_bafu_datasets",
                    "arguments": {"params": {"query": "luft"}},
                    "_meta": meta,
                },
            },
            headers=modern_headers("tools/call", "env_bafu_datasets"),
        )


async def test_ohne_opt_in_sendet_der_server_keine_logmeldung(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die MUST-NOT-Seite der Spec.

    Kein `logLevel` im Umschlag: Die Antwort bleibt `application/json` und
    traegt kein `notifications/message`. Und — der eigentliche Punkt — der
    Aufruf bricht daran nicht ab: Er liefert regulaer `isError`, samt der
    maskierten Meldung, die das Modell lesen soll.
    """
    monkeypatch.setattr(api, "dns_pin_enabled", False)

    response = await _failing_tool_call(client, None)

    assert response.headers["content-type"].startswith("application/json"), response.headers
    assert "notifications/message" not in response.text
    result = result_of(response)
    assert result["isError"] is True, result
    assert result["content"][0]["text"].strip(), "die maskierte Meldung fehlt"


async def test_mit_opt_in_kommt_die_logmeldung_an(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe — und der Grund, warum `ctx.warning` stehen bleibt.

    `ctx.warning` traegt im SDK ein `@deprecated` (SEP-2577). Daraus zu
    schliessen, der Kanal sei tot, und die Zeile zu streichen, waere ein
    Fehlbefund: Die Deprecation gilt der Capability-Aera-API, nicht dem
    Mechanismus. Mit Opt-in wechselt dieselbe Anfrage auf `text/event-stream`
    — der Strom traegt die Meldung vor dem Resultat.

    Faellt dieser Test nach einem SDK-Bump, ist zuerst zu messen, ob der
    Mechanismus weg ist oder nur der Helfer umbenannt wurde. Die Antwort
    entscheidet, ob `_handle_tool_error` einen Ersatz braucht oder die Zeile
    tatsaechlich entfallen darf.
    """
    monkeypatch.setattr(api, "dns_pin_enabled", False)

    response = await _failing_tool_call(client, "warning")

    assert response.headers["content-type"].startswith("text/event-stream"), response.headers
    assert "notifications/message" in response.text, response.text[:400]
    assert "env_bafu_datasets" in response.text


def test_der_opt_in_schluessel_ist_der_reservierte_name() -> None:
    """Der Schluessel oben ist reserviert; ein selbstgewaehlter Name waere ein
    Opt-in, das kein Client je auslöst — und beide Tests blieben gruen."""
    assert LOG_LEVEL_META_KEY == "io.modelcontextprotocol/logLevel"


# --- Nicht nur HTTP: der Standard-Transport dieses Servers ist stdio ----------


async def test_die_moderne_aera_gilt_auch_abseits_von_http() -> None:
    """Die Tests oben messen alle den HTTP-Transport — `MCP_TRANSPORT` defaultet
    hier aber auf stdio.

    Waere die moderne Aera nur ueber HTTP belegt, stuende die *Standard*-
    Auslieferung ungemessen da. Der In-Memory-Client nimmt denselben
    Dispatch-Pfad wie stdio (`mcp.server.runner`, nicht der
    Streamable-HTTP-Einstieg) und zeigt beides: dass modern ausgehandelt wird
    und dass die Identitaet auch dort ankommt.

    Die schwaechere Form, benannt statt verschwiegen: Das ist kein echter
    Subprozess ueber Pipes. Was hier nicht abgedeckt ist, ist das
    Rahmen/Zeilen-Format von stdio — wohl aber alles, was dieser Server dazu
    beitraegt.
    """
    async with Client(mcp) as client:
        assert client.protocol_version == MODERN, client.protocol_version

        info = client.server_info
        assert info is not None
        assert info.version == __version__, info.version
        assert info.title == SERVER_TITLE
