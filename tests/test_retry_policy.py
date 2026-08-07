"""Tests für die Retry-Politik beider Client-Pfade (ARCH-014).

Ein Portfolio-Durchlauf des Audit-Katalogs am 2026-08-07 las beide Schleifen
von Hand. Keiner der beiden Pfade streute seinen Backoff, keiner las
``Retry-After``, keiner hatte eine Zeitgrenze.

Der Weg dorthin war bei den beiden verschieden, und das ist der eigentliche
Befund:

* ``sparql_client.py`` ist eine **vendored copy**, die laut ihrem eigenen Kopf
  byte-identisch mit ``fedlex-mcp`` sein soll. Sie war es nicht mehr — dort war
  die Reparatur schon geschehen, hier nicht, und der Versionsmarker ``v1.1.0``
  stand auf beiden Seiten unverändert. Die Datei ist jetzt wieder
  byte-identisch übernommen.
* ``lindas/client.py`` hat eine eigene Schleife und wurde hier repariert, mit
  denselben Helfern aus dem vendorierten Modul statt einer zweiten Kopie.

Jede Eigenschaft hat eine Gegenprobe.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from swiss_environment_mcp import sparql_client
from swiss_environment_mcp.lindas import client as lindas

ENDPOINT = "https://ld.admin.ch/query"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    """Nullt die Wartezeit, ohne ``asyncio.sleep`` prozessweit stillzulegen.

    Gepatcht wird ``lindas._sleep``. Ein
    ``monkeypatch.setattr(lindas.asyncio, "sleep", ...)`` sähe lokal aus und
    trifft das stdlib-Modul — jeder Test, der ``asyncio.sleep`` benutzt, um dem
    Event-Loop das Wort zu geben, misst danach nichts mehr und bleibt grün.
    ``test_die_fixture_laesst_das_echte_asyncio_sleep_in_ruhe`` bewacht die Naht.
    """

    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(lindas, "_sleep", _instant)


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    # Die Request-Instanz gehört dran: ohne sie wirft `raise_for_status()`
    # einen RuntimeError statt des HTTPStatusError, auf den der Code verzweigt.
    return httpx.Response(
        status,
        headers=headers,
        request=httpx.Request("GET", ENDPOINT),
        json={"results": {"bindings": []}},
    )


def _err(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    resp = _resp(status, retry_after)
    return httpx.HTTPStatusError("x", request=resp.request, response=resp)


# --- Die vendored copy trägt die Eigenschaften wieder ------------------------


def test_retry_after_liest_sekundenzahl():
    assert sparql_client.parse_retry_after(_resp(429, "120")) == 120.0


def test_retry_after_liest_ein_http_datum():
    when = datetime.now(UTC) + timedelta(seconds=60)
    got = sparql_client.parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
    assert got is not None
    assert 55 <= got <= 61


@pytest.mark.parametrize("raw", ["", "   ", "bald", "kein-datum"])
def test_unlesbarer_retry_after_faellt_zurueck_statt_zu_werfen(raw):
    assert sparql_client.parse_retry_after(_resp(429, raw)) is None


def test_retry_after_wird_ignoriert_wo_er_nichts_bedeutet():
    assert sparql_client.parse_retry_after(_resp(500, "120")) is None
    assert sparql_client.parse_retry_after(None) is None


def test_die_wartezeit_ist_gestreut():
    draws = {sparql_client.retry_delay(1, None, 2.0) for _ in range(50)}
    assert len(draws) > 1, "ein Gleichtakt-Backoff kommt als Welle zurück"


def test_ein_retry_after_wird_einseitig_gestreut():
    draws = [sparql_client.retry_delay(1, _err(429, "10"), 2.0) for _ in range(50)]
    assert len(set(draws)) > 1
    assert all(10.0 <= d <= 12.5 for d in draws), sorted(draws)[:3]


def test_der_deckel_ist_eine_echte_schranke_kein_mittelwert():
    # Jitter ist zufällig — eine Ziehung beweist nichts.
    for attempt in range(1, 9):
        for _ in range(25):
            assert sparql_client.retry_delay(attempt, None, 2.0) <= sparql_client.MAX_DELAY_S
            assert (
                sparql_client.retry_delay(attempt, _err(429, "86400"), 2.0)
                <= sparql_client.MAX_DELAY_S
            )


def test_deckel_vor_dem_jitter_waere_keine_schranke():
    """Gegenprobe zur Reihenfolge, damit der Test darüber fallen kann."""
    broken = min(2.0 * 2**7, sparql_client.MAX_DELAY_S) * 1.5
    assert broken > sparql_client.MAX_DELAY_S


def test_die_vendored_copy_traegt_ein_wanduhr_budget():
    assert sparql_client.TOTAL_BUDGET_S > 0


# --- Der LINDAS-Pfad ---------------------------------------------------------


class _Http:
    """Minimaler AsyncClient-Ersatz mit vorgegebener Antwortfolge."""

    def __init__(self, items: list):
        self.items = items
        self.calls = 0

    async def get(self, *_a, **_k):
        item = self.items[min(self.calls, len(self.items) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return item

    post = get


async def test_lindas_wiederholt_einen_500(monkeypatch):
    """Der Kernbefund am Status-Set: 500 fehlte in RETRYABLE_STATUS.

    Ein überlastetes Gateway antwortet nicht immer mit 502 — ein 500 ist
    genauso eine Aussage über den Moment.
    """
    assert 500 in lindas.RETRYABLE_STATUS
    http = _Http([_resp(500), _resp(200)])
    assert await lindas.select(http, "SELECT * {}", base_delay=0.0) == []
    assert http.calls == 2


async def test_lindas_wiederholt_einen_429():
    http = _Http([_resp(429), _resp(200)])
    assert await lindas.select(http, "SELECT * {}", base_delay=0.0) == []
    assert http.calls == 2


async def test_lindas_wiederholt_einen_verbindungsfehler():
    http = _Http([httpx.ConnectError("refused"), _resp(200)])
    assert await lindas.select(http, "SELECT * {}", base_delay=0.0) == []
    assert http.calls == 2


async def test_lindas_wiederholt_die_requesterror_oberklasse():
    """Bisher nur ConnectError und ReadError — ein anderer Abbruch entkam."""
    http = _Http([httpx.WriteError("abgerissen"), _resp(200)])
    assert await lindas.select(http, "SELECT * {}", base_delay=0.0) == []
    assert http.calls == 2


async def test_lindas_reicht_ein_400_sofort_durch():
    http = _Http([_resp(400)])
    with pytest.raises(lindas.QueryError):
        await lindas.select(http, "SELECT * {}", base_delay=0.0)
    assert http.calls == 1, "auch der vierte Versuch macht aus einem 400 kein 200"


async def test_lindas_begrenzt_die_versuche():
    http = _Http([_resp(503)])
    with pytest.raises(httpx.HTTPStatusError):
        await lindas.select(http, "SELECT * {}", base_delay=0.0)
    assert http.calls == lindas.DEFAULT_MAX_ATTEMPTS


async def test_lindas_nutzt_den_retry_after(monkeypatch):
    seen: list[float] = []

    async def _record(seconds: float) -> None:
        seen.append(seconds)

    monkeypatch.setattr(lindas, "_sleep", _record)
    http = _Http([_resp(503, "7"), _resp(200)])
    await lindas.select(http, "SELECT * {}", base_delay=2.0)
    assert seen and 7.0 <= seen[0] <= 8.75, seen


# --- Das Budget, an der Wanduhr gemessen -------------------------------------


async def test_lindas_wird_von_der_wanduhr_geschnitten():
    """Die Zusicherung, die eine Fake-Uhr nicht widerlegen kann.

    Eine Uhr, die nur beim Schlafen vorrückt, kann eine Aussage über *echte*
    Zeit nicht widerlegen: Der Code, der die Wanduhr ignoriert, schläft nicht,
    also vergeht keine Zeit, also bleibt die kaputte Fassung grün. Dieser Test
    schläft deshalb echt — bewusst, und als einziger hier.
    """

    class _Slow:
        calls = 0

        async def get(self, *_a, **_k):
            await asyncio.sleep(0.30)
            return _resp(200)

        post = get

    started = time.monotonic()
    with pytest.raises(lindas.QueryTimeoutError):
        await lindas.select(_Slow(), "SELECT * {}", base_delay=0.0, total_budget=0.05)
    assert time.monotonic() - started < 0.25, "QUERY_TIMEOUT_SECONDS ist kein Budget"


async def test_eine_wartezeit_ueber_dem_budget_wird_nicht_genommen(monkeypatch):
    monkeypatch.setattr(lindas, "retry_delay", lambda *_a, **_k: 999.0)
    http = _Http([_resp(503)])
    with pytest.raises(httpx.HTTPStatusError):
        await lindas.select(http, "SELECT * {}", base_delay=2.0, total_budget=1.0)
    assert http.calls == 1


# --- Die Naht ----------------------------------------------------------------


async def test_die_fixture_laesst_das_echte_asyncio_sleep_in_ruhe():
    """Bewacht die Naht, die die autouse-Fixture patcht.

    ``monkeypatch.setattr(lindas.asyncio, "sleep", ...)`` sähe lokal aus und
    legt das Schlafen prozessweit still — samt fremder Tests, die damit dem
    Event-Loop das Wort geben. Genau so ist in ``srgssr-mcp`` eine
    Parallelitäts-Prüfung eingebrochen, ohne rot zu werden.
    """
    started = time.monotonic()
    await asyncio.sleep(0.05)
    assert time.monotonic() - started >= 0.04, "asyncio.sleep ist prozessweit ausser Kraft"


# --- Die beiden Kopien müssen zusammenbleiben --------------------------------


def test_die_vendored_copy_ist_nicht_wieder_auseinandergelaufen():
    """Der Grund, warum dieser Server die Reparatur verpasst hat.

    ``sparql_client.py`` sagt von sich, byte-identisch mit der Kopie in
    ``fedlex-mcp`` zu sein. Genau das stimmte nicht mehr, und der
    Versionsmarker im Kopf stand auf beiden Seiten unverändert auf ``v1.1.0``
    — es gab also nichts, was den Unterschied hätte melden können.

    Dieser Test kann die Schwesterkopie von hier aus nicht sehen. Was er halten
    kann, ist die Menge der Eigenschaften, die eine Synchronisierung nicht
    verlieren darf: Wer eine davon entfernt, hat die Kopien wieder getrennt.
    """
    for name in ("parse_retry_after", "retry_delay", "MAX_DELAY_S", "TOTAL_BUDGET_S"):
        assert hasattr(sparql_client, name), (
            f"`{name}` fehlt — die vendored copy ist gegenüber fedlex-mcp "
            "zurückgefallen, so wie schon einmal"
        )
