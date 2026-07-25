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
from collections.abc import Callable
from typing import Any

import httpx

LINDAS_ENDPOINT = "https://lindas.admin.ch/query"

# Portfolio-Standard: Retry 2 s/4 s/8 s, 4xx (ausser 429) ohne Retry.
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_DELAY = 2.0  # Sekunden; Waits base*2**attempt → 2/4/8. Tests: 0.

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
    egress_check: Callable[[str], None] | None = None,
    on_retry: Callable[[int, str, Exception], None] | None = None,
) -> list[dict[str, str]]:
    """Führt eine SELECT-Query aus und liefert flache Result-Dicts.

    GET für kurze, POST (`application/sparql-query`) für lange Queries.
    Retry nur bei transienten Fehlern (429/5xx, Timeout/Netzwerk) mit
    exponentiellem Backoff; HTTP 400 wird sofort als `QueryError` mit der
    Server-Meldung durchgereicht, andere 4xx als `QueryError` mit Status.
    """
    if egress_check is not None:
        egress_check(endpoint)

    timeout = httpx.Timeout(QUERY_TIMEOUT_SECONDS, connect=5.0)
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
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
        except httpx.TimeoutException as e:
            last_exc = QueryTimeoutError()
            last_exc.__cause__ = e
        except (httpx.ConnectError, httpx.ReadError) as e:
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
        if attempt < max_attempts - 1:
            if on_retry is not None:
                on_retry(attempt + 1, endpoint, last_exc)
            await asyncio.sleep(base_delay * (2**attempt))
    assert last_exc is not None  # pragma: no cover - Schleife garantiert gesetzt
    raise last_exc
