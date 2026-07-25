"""Tests für das extraktionsfähige `lindas/`-Modul (Phase 2 der Hydro-Erweiterung).

Abgedeckt gemäss Auftrag:
  - client.py via respx: Happy Path, 400 MALFORMED → QueryError, Timeout →
    klare Meldung (statt Server-«HTTP 000»), Retry auf 503, POST für lange Queries.
  - cube.py rein (ohne Mocks): Versions-Deduplizierung, Code→Label-Auflösung,
    pick_lang, URI-Guards.
  - Tool-Pfad env_bathing_water via respx (Aufrufer sieht Labels, nie Codes).
"""

import httpx
import pytest
import respx

from swiss_environment_mcp import api_client as api
from swiss_environment_mcp.lindas import client as lc
from swiss_environment_mcp.lindas import cube as lcube
from swiss_environment_mcp.server import BathingWaterInput, env_bathing_water

_URL = lc.LINDAS_ENDPOINT


def _sparql(rows: list[dict], lang: dict[str, str] | None = None) -> dict:
    """SPARQL-results+json aus {var: value}-Zeilen; `lang` taggt Variablen."""
    bindings = []
    for row in rows:
        b = {}
        for k, v in row.items():
            entry: dict = {"value": str(v)}
            if lang and k in lang:
                entry["xml:lang"] = lang[k]
            b[k] = entry
        bindings.append(b)
    return {"results": {"bindings": bindings}}


@pytest.fixture(autouse=True)
def _no_dns_pin(monkeypatch):
    monkeypatch.setattr(api, "dns_pin_enabled", False)


@pytest.fixture()
def http():
    return httpx.AsyncClient()


# --- client.py ------------------------------------------------------------------


@respx.mock
async def test_client_happy_path_flat_dicts(http):
    """SELECT liefert flache Dicts; Sprach-Tags als <var>__lang."""
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200, json=_sparql([{"name": "Clendy", "id": "CH22088"}], lang={"name": "fr"})
        )
    )
    rows = await lc.select(http, "SELECT ?name ?id WHERE { ?s ?p ?o }")
    assert rows == [{"name": "Clendy", "name__lang": "fr", "id": "CH22088"}]


@respx.mock
async def test_client_400_malformed_raises_query_error(http):
    """HTTP 400 → QueryError MIT der MALFORMED-Meldung, ohne Retry."""
    route = respx.get(_URL).mock(
        return_value=httpx.Response(400, text='MALFORMED QUERY: Encountered "<EOF>"')
    )
    with pytest.raises(lc.QueryError) as exc:
        await lc.select(http, "SELECT ?x WHERE { ?x", base_delay=0)
    assert "MALFORMED" in str(exc.value)
    assert exc.value.status_code == 400
    assert route.call_count == 1


@respx.mock
async def test_client_timeout_clear_message(http):
    """Timeout → QueryTimeoutError mit klarer Meldung (kein nacktes «HTTP 000»)."""
    respx.get(_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(lc.QueryTimeoutError) as exc:
        await lc.select(http, "SELECT 1", base_delay=0, max_attempts=2)
    assert "45 s" in str(exc.value)
    assert "verankerte" in str(exc.value)


@respx.mock
async def test_client_retry_on_503(http):
    """Transienter 503 wird retried; zweiter Versuch erfolgreich."""
    route = respx.get(_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_sparql([{"x": "1"}]))]
    )
    rows = await lc.select(http, "SELECT 1", base_delay=0)
    assert rows == [{"x": "1"}]
    assert route.call_count == 2


@respx.mock
async def test_client_long_query_uses_post(http):
    """Lange Queries gehen als POST application/sparql-query."""
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_sparql([])))
    long_query = "SELECT * WHERE { ?s ?p ?o }" + " " * 2000
    await lc.select(http, long_query)
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["content-type"] == "application/sparql-query"


# --- cube.py: pure Funktionen ---------------------------------------------------


def test_version_dedup_latest_wins():
    """Mehrere Cube-Versionen → die neueste gewinnt (Fundstück 5)."""
    cubes = [
        {"cube": "https://example.ch/foen/ubd0104/2/", "version": "2"},
        {"cube": "https://example.ch/foen/ubd0104/13", "version": "13"},
        {"cube": "https://example.ch/foen/ubd0104/4/", "version": "4"},
        {"cube": "https://example.ch/foen/hydro/river"},  # unversioniert
    ]
    latest = lcube.dedupe_latest_versions(cubes)
    uris = [c["cube"] for c in latest]
    assert "https://example.ch/foen/ubd0104/13" in uris
    assert "https://example.ch/foen/hydro/river" in uris
    assert len(uris) == 2  # 3 Versionen → 1; river separat


def test_version_dedup_uri_suffix_fallback():
    """Ohne schema:version entscheidet das (Slash-tolerante) URI-Suffix."""
    cubes = [
        {"cube": "https://example.ch/c/9/"},
        {"cube": "https://example.ch/c/10"},
    ]
    assert lcube.dedupe_latest_versions(cubes)[0]["cube"] == "https://example.ch/c/10"


def test_resolve_codes_label_and_join_keys():
    """Roher Code rein, Label raus — plus Kantonsnummer/BFS als Join-Keys."""
    rows = [{"location": "https://ld.admin.ch/x/CH22088", "value": "5080"}]
    labels = {
        "https://ld.admin.ch/x/CH22088": {
            "label": "Clendy",
            "identifier": "CH22088",
            "contained_in": "https://ld.admin.ch/canton/22",
        }
    }
    out = lcube.resolve_codes(rows, labels)[0]
    assert out["location"] == "Clendy"
    assert out["location_code"] == "CH22088"
    assert out["location_canton_number"] == 22
    assert out["value"] == "5080"  # Literale bleiben unangetastet


def test_resolve_codes_bfs_number_from_municipality_uri():
    """Gemeinde-URI trägt die BFS-Nummer im Klartext (Fundstück 3)."""
    rows = [{"gemeinde": "https://ld.admin.ch/municipality/261"}]
    labels = {"https://ld.admin.ch/municipality/261": {"label": "Zürich"}}
    out = lcube.resolve_codes(rows, labels)[0]
    assert out["gemeinde"] == "Zürich"
    assert out["gemeinde_bfs_number"] == 261


def test_pick_lang_preference_and_fallback():
    assert lcube.pick_lang({"de": "Fluss", "fr": "Rivière"}, "fr") == "Rivière"
    assert lcube.pick_lang({"fr": "Rivière", "en": "River"}, "de") == "River"
    assert lcube.pick_lang({"rm": "Flum"}, "de") == "Flum"
    assert lcube.pick_lang({}, "de") == ""


def test_safe_uri_rejects_injection():
    with pytest.raises(ValueError):
        lcube._safe_uri("https://x.ch/a> } . ?s ?p ?o . { <https://x.ch/b")


# --- cube.py: Guardrail-Queries gegen gemockten Endpoint ------------------------


@respx.mock
async def test_get_observations_uses_observation_set_path():
    """Phase-2-Query enthält den observationSet-Zwischenschritt (Fundstück 6)."""
    captured: list[str] = []

    async def run(query: str) -> list[dict[str, str]]:
        captured.append(query)
        return []

    await lcube.get_observations(run, "https://example.ch/cube/1", limit=5)
    assert "cube:observationSet" in captured[0]
    assert "cube:observation ?obs" in captured[0]


@respx.mock
async def test_get_cube_license_undeclared_is_honest():
    """Ohne Lizenz-Triple kommt der ehrliche Hinweis, keine Open-Use-Annahme."""

    async def run(query: str) -> list[dict[str, str]]:
        return []

    result = await lcube.get_cube_license(run, "https://example.ch/cube/1")
    assert result == lcube.LICENSE_UNDECLARED
    assert "opendata.swiss" in result


# --- Tool-Pfad env_bathing_water ------------------------------------------------

_CUBE = "https://environment.ld.admin.ch/foen/ubd01041prod/13"
_DIM = "https://environment.ld.admin.ch/foen/ubd01041prod/"
_LOC = "https://ld.admin.ch/dimension/bgdi/inlandwaters/bathingwater/CH22088"


def _bathing_side_effects() -> list[httpx.Response]:
    """Antwort-Sequenz: find_cubes, license, find_dimension_values,
    Observations (Triples), Label-Resolution."""
    return [
        httpx.Response(
            200,
            json=_sparql(
                [{"cube": _CUBE, "name": "Qualität der Badegewässer", "version": "13"}],
                lang={"name": "de"},
            ),
        ),
        httpx.Response(
            200,
            json=_sparql([{"license": "https://ld.admin.ch/vocabulary/TermsOfUse/Open-Use"}]),
        ),
        httpx.Response(
            200,
            json=_sparql(
                [
                    {
                        "value": _LOC,
                        "name": "Clendy",
                        "nameLang": "fr",
                        "identifier": "CH22088",
                        "place": "https://ld.admin.ch/canton/22",
                    }
                ]
            ),
        ),
        httpx.Response(
            200,
            json=_sparql(
                [
                    {"obs": "o1", "p": f"{_DIM}dateofprobing", "o": "2025-09-23"},
                    {"obs": "o1", "p": f"{_DIM}parametertype", "o": "E.coli"},
                    {"obs": "o1", "p": f"{_DIM}value", "o": "5080"},
                    {"obs": "o1", "p": f"{_DIM}location", "o": _LOC},
                ]
            ),
        ),
        httpx.Response(
            200,
            json=_sparql(
                [
                    {
                        "code": _LOC,
                        "label": "Clendy",
                        "labelLang": "fr",
                        "identifier": "CH22088",
                        "place": "https://ld.admin.ch/canton/22",
                    }
                ]
            ),
        ),
    ]


@respx.mock
async def test_bathing_water_resolves_codes_to_labels():
    """Aufrufer sieht Label + Kantonsnummer, nie die rohe Code-URI."""
    respx.get(_URL).mock(side_effect=_bathing_side_effects())
    out = await env_bathing_water(BathingWaterInput(location="Clendy"))
    assert "Clendy" in out
    assert "CH22088" in out  # Kurz-Code als Join-Key ist ok
    assert "VD" in out  # Kanton 22 aufgelöst
    assert "E.coli" in out and "5080" in out
    assert _LOC not in out  # rohe Code-URI erscheint nie
    assert "Open-Use" in out  # Lizenzfeld in der Antwort


@respx.mock
async def test_bathing_water_unknown_location_actionable():
    """Kein Treffer → match_type none mit actionable Hinweis."""
    respx.get(_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json=_sparql(
                    [{"cube": _CUBE, "name": "Qualität der Badegewässer", "version": "13"}],
                    lang={"name": "de"},
                ),
            ),
            httpx.Response(200, json=_sparql([{"license": "x"}])),
            httpx.Response(200, json=_sparql([])),
        ]
    )
    out = await env_bathing_water(BathingWaterInput(location="Atlantis"))
    assert "match_type: none" in out


@respx.mock
async def test_bathing_water_upstream_down_raises_tool_error(monkeypatch):
    """LINDAS down → terminaler Fehler als ToolError (isError:true, OBS-001),
    Fehler-Content trägt weiterhin den Direktzugang statt eines Stacktrace."""
    from mcp.server.fastmcp.exceptions import ToolError

    monkeypatch.setattr(api, "LINDAS_RETRY_BASE_DELAY", 0)
    respx.get(_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ToolError) as exc:
        await env_bathing_water(BathingWaterInput(location="Clendy"))
    msg = str(exc.value)
    assert "nicht abrufbar" in msg
    assert "Direktzugang" in msg
