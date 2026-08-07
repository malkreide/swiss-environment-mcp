"""
Async SPARQL-Client für https://lindas.admin.ch/query — Schicht 1 von 3.

Diese Schicht kennt NUR SPARQL und HTTP: Transport (GET/POST), Timeout,
Retry und die Übersetzung der SPARQL-JSON-Bindings in flache Dicts.
Sie kennt weder cube.link noch irgendein Domänen-Vokabular (das ist
`cube.py`) und wird von den MCP-Tools nie direkt aufgerufen.

Empirisch verankerte Entscheide (docs/probe-lindas-hydro.md):
  - Client-seitiger Timeout 45 s: Der LINDAS-Server bricht Langläufer erst
    nach 60–90 s selbst ab und liefert dann eine leere Antwort («HTTP 000»
    aus curl-Sicht). Wir schlagen vorher mit einer klaren Meldung fehl.
  - HTTP 400 trägt die MALFORMED-QUERY-Meldung im Body — sie wird als
    `QueryError` durchgereicht, nicht als generischer Upstream-Fehler
    verschluckt (die Meldung nennt die fehlerhafte Stelle der Query).
  - Kurze Queries per GET (cache-freundlich), lange per POST mit
    `Content-Type: application/sparql-query` (GET-URLs sind längenbegrenzt).

Wie `sparql_client.py` ist das Modul bewusst abhängigkeitsarm (nur `httpx`,
`asyncio`); Egress-Guard und HTTP-Client werden vom Aufrufer injiziert,
damit das Modul 1:1 nach `lindas-mcp` hebbar bleibt.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..sparql_client import retry_delay

LINDAS_ENDPOINT = "https://lindas.admin.ch/query"

# Portfolio-Standard: Retry 2 s/4 s/8 s, 4xx (ausser 429) ohne Retry.
# 500 gehoert dazu: Ein ueberlastetes Gateway antwortet nicht immer mit 502.
# ARCH-014 nennt die wiederholbare Menge als 5xx, 429, Timeout und
# Verbindungsfehler — hier fehlte bisher genau die 500.
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_DELAY = 2.0  # Sekunden; Leiter vor dem Jitter: 2/4/8. Tests: 0.

# Deckel auf den GESAMTEN Aufruf — alle Versuche und alle Wartezeiten zusammen
# (ARCH-014). Eine Versuchszahl ist keine Grenze: Vier Versuche gegen einen
# Endpunkt, der die vollen QUERY_TIMEOUT_SECONDS (45 s) braucht, sind drei
# Minuten in einem Tool-Aufruf, und DEFAULT_MAX_ATTEMPTS sagt das nirgends.
# Das httpx-Timeout ist kein Budget: Es begrenzt pro Operation, und sein
# Read-Timeout beginnt mit jedem Chunk von vorn.
#
# 45 s statt der 25 s der uebrigen Server: SPARQL-Abfragen gegen LINDAS
# laufen laenger als ein REST-Aufruf, und derselbe Wert steht im
# vendorierten `sparql_client`. Wer ihn senkt, senkt ihn dort mit.
TOTAL_BUDGET_S = 45.0

# Indirektion, damit Tests die Wartezeit nullen koennen, ohne `asyncio.sleep`
# selbst zu patchen. Ein `monkeypatch.setattr(client.asyncio, "sleep", ...)`
# saehe lokal aus und ist es nicht: `client.asyncio` *ist* das stdlib-Modul,
# der Patch legt das Schlafen prozessweit still — samt fremder Tests, die damit
# dem Event-Loop das Wort geben und danach nichts mehr messen.
_sleep = asyncio.sleep

# Client-seitiger Query-Timeout (siehe Modul-Docstring).
QUERY_TIMEOUT_SECONDS = 45.0

# Ab dieser Query-Länge POST statt GET (URL-Längenlimits von Proxies/Servern).
_GET_MAX_QUERY_CHARS = 1500

_RESULTS_MIME = "application/sparql-results+json"


class LindasError(Exception):
    """Basisklasse aller Fehler dieses Clients."""


class QueryError(LindasError):
    """Deterministischer Query-Fehler (HTTP 400, z.B. MALFORMED QUERY).

    Trägt die Server-Fehlermeldung — sie benennt die fehlerhafte Stelle der
    Query und ist damit die wertvollste Debug-Information. Kein Retry.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class QueryTimeoutError(LindasError):
    """Client-seitiger Timeout (45 s) — VOR dem Server-Abbruch bei 60–90 s.

    Tritt typischerweise bei nicht am Vokabular verankerten Queries auf
    (Blind-Scans); die Meldung sagt das explizit.
    """

    def __init__(self) -> None:
        super().__init__(
            f"LINDAS-Query nach {QUERY_TIMEOUT_SECONDS:.0f} s clientseitig abgebrochen "
            "(der Server selbst bricht erst nach 60–90 s ohne verwertbare Antwort ab). "
            "Ursache ist meist eine nicht am Vokabular verankerte Query."
        )


def parse_bindings(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Übersetzt SPARQL-JSON-Bindings in flache Dicts (Variable → Wert).

    Sprach-Tags werden nicht verworfen, sondern als eigene Pseudo-Variable
    `<var>__lang` abgelegt — so kann die Cube-Schicht `pick_lang` anwenden,
    ohne dass diese Schicht Sprachlogik kennen muss.
    """
    rows: list[dict[str, str]] = []
    for binding in payload.get("results", {}).get("bindings", []):
        row: dict[str, str] = {}
        for var, entry in binding.items():
            row[var] = entry.get("value", "")
            lang = entry.get("xml:lang")
            if lang:
                row[f"{var}__lang"] = lang
        rows.append(row)
    return rows


async def select(
    http: httpx.AsyncClient,
    query: str,
    *,
    endpoint: str = LINDAS_ENDPOINT,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    total_budget: float = TOTAL_BUDGET_S,
    egress_check: Callable[[str], None] | None = None,
    on_retry: Callable[[int, str, Exception], None] | None = None,
) -> list[dict[str, str]]:
    """Führt eine SELECT-Query aus und liefert flache Result-Dicts.

    GET für kurze, POST (`application/sparql-query`) für lange Queries.
    Retry nur bei transienten Fehlern (429/5xx, Timeout/Netzwerk). Jede
    Wartezeit ist gestreut und gedeckelt; ein `Retry-After` auf 429/503 schlaegt
    die eigene Kurve (`sparql_client.retry_delay`). Der ganze Aufruf ist durch
    `total_budget` Sekunden Wanduhrzeit begrenzt. HTTP 400 wird sofort als
    `QueryError` mit der Server-Meldung durchgereicht, andere 4xx als
    `QueryError` mit Status.
    """
    if egress_check is not None:
        egress_check(endpoint)

    timeout = httpx.Timeout(QUERY_TIMEOUT_SECONDS, connect=5.0)
    last_exc: Exception | None = None
    deadline = time.monotonic() + total_budget
    for attempt in range(max_attempts):
        if attempt > 0:
            delay = retry_delay(attempt, last_exc, base_delay)
            # Eine Wartezeit, die das Budget ueberdauert, ist eine Wartezeit
            # fuer niemanden: Der Aufrufer hat aufgegeben, bevor sie endet.
            if delay >= deadline - time.monotonic():
                break
            if on_retry is not None:
                on_retry(attempt, endpoint, last_exc)
            await _sleep(delay)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # `asyncio.timeout` ist die Wanduhr-Deadline, die das Budget
            # zusagt; das httpx-Timeout bleibt daneben die Schranke je
            # Operation.
            async with asyncio.timeout(remaining):
                if len(query) <= _GET_MAX_QUERY_CHARS:
                    response = await http.get(
                        endpoint,
                        params={"query": query, "format": _RESULTS_MIME},
                        headers={"Accept": _RESULTS_MIME},
                        timeout=timeout,
                    )
                else:
                    response = await http.post(
                        endpoint,
                        content=query.encode("utf-8"),
                        headers={
                            "Content-Type": "application/sparql-query",
                            "Accept": _RESULTS_MIME,
                        },
                        timeout=timeout,
                    )
        except TimeoutError as e:  # Budget weg, nicht bloss dieser Versuch
            last_exc = QueryTimeoutError()
            last_exc.__cause__ = e
            break
        except httpx.TimeoutException as e:
            last_exc = QueryTimeoutError()
            last_exc.__cause__ = e
        except (httpx.ConnectError, httpx.ReadError, httpx.RequestError) as e:
            last_exc = e
        else:
            status = response.status_code
            if status < 400:
                return parse_bindings(response.json())
            if status in RETRYABLE_STATUS:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {status}", request=response.request, response=response
                )
            else:
                # Deterministisch (4xx ausser 429): Server-Meldung durchreichen.
                detail = response.text.strip() or f"HTTP {status} ohne Fehlermeldung"
                raise QueryError(detail, status_code=status)
    assert last_exc is not None  # pragma: no cover - Schleife garantiert gesetzt
    raise last_exc
