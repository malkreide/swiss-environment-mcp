"""Gemeinsame Test-Fixtures und -Hooks für alle Test-Module.

Kern-Problem (SDK-001): `api_client` hält einen einzelnen, modul-globalen
`httpx.AsyncClient`. Unter `pytest-asyncio` mit Standard-Loop-Scope `function`
läuft jeder Test in einem **eigenen** Event Loop. Ein in Test A erzeugter
Client (samt seiner gepoolten Verbindungen) würde ohne Reset in Test B
weiterverwendet — gebunden an den inzwischen geschlossenen Loop von Test A.
Sobald der Pool eine solche veraltete Verbindung schliesst (z.B. beim Prunen
idle gewordener Keep-Alive-Verbindungen eines anderen Hosts), ruft httpx
`loop.call_soon()` auf dem toten Loop auf → `RuntimeError: Event loop is closed`.

Genau dieser Effekt liess `test_slf_snow` (nach dem LINDAS-Test) live scheitern.

Die autouse-Fixture setzt den geteilten Client vor und nach **jedem** Test
zurück. Damit bleibt jeder Client — und jede seiner Verbindungen — an den Loop
gebunden, der ihn erzeugt hat. DNS-Pinning wird bewusst NICHT angefasst: die
Live-Tests treffen echte Hosts und sind auf Pinning + Egress-Guard angewiesen.
(`test_unit.py` deaktiviert Pinning zusätzlich in einer eigenen Fixture, damit
die respx-Mocks greifen.)

Zweites Thema in dieser Datei: der `live`-Marker (OPS-001). Die so markierten
Tests prüfen den **Vertrag** echter Fremd-APIs und laufen nur nächtlich. Ein
reiner Transportfehler (die Gegenstelle nahm die Verbindung nicht an) ist dabei
kein Vertragsbruch — siehe `pytest_runtest_makereport` weiter unten.
"""

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp import api_client as _api


@pytest.fixture(autouse=True)
async def _reset_shared_http_client():
    """Frischer geteilter AsyncClient je Test, sauber auf dem eigenen Loop geschlossen."""
    await _api.shutdown()
    yield
    await _api.shutdown()


# --- Live-Tests: Upstream-Ausfall ist kein Vertragsbruch (OPS-001) ------------
#
# Der nächtliche Live-Lauf überwacht, ob die Fremd-APIs noch das liefern, was
# dieser Server aus ihnen liest. Ging die Verbindung gar nicht erst zustande,
# beantwortet der Lauf diese Frage nicht — er scheiterte an der Leitung. Genau
# das riss `test_slf_snow` mehrfach rot (`httpx.ConnectTimeout` gegen
# `measurement-api.slf.ch`, zuletzt am 03.08.2026), während dieselbe API kurz
# davor und danach antwortete.
#
# Solche Läufe werden deshalb übersprungen statt als Fehler gewertet — aber
# sichtbar: `pytest_terminal_summary` schreibt am Ende einen eigenen Block, und
# im `-v`-Protokoll steht `SKIPPED` mit Grund. Wiederholt sich derselbe Host
# über mehrere Nächte, ist der Dienst tatsächlich weg und gehört untersucht.
#
# Bewusst NICHT übersprungen wird alles, was eine Antwort voraussetzt: HTTP-
# Status-Fehler (4xx/5xx), geändertes Schema, verletzte Assertions, ein
# `SecurityError` des Egress-Guards. Das sind echte Befunde.

_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)

# Gesammelte Übersprungen-Meldungen für die Terminal-Zusammenfassung.
_UPSTREAM_SKIPS: pytest.StashKey[list[str]] = pytest.StashKey()


def _transport_cause(exc: BaseException | None) -> BaseException | None:
    """Sucht in der Exception-Kette den ersten reinen Transportfehler.

    Die Kette wird mitgelaufen, weil die Tools den Transportfehler einpacken:
    `env_snow_stations` wirft einen `ToolError` (mit dem httpx-Fehler als
    `__context__`), der LINDAS-Client einen `QueryTimeoutError` (mit gesetztem
    `__cause__`). Ohne Kettenlauf würde nur der direkte API-Aufruf erkannt.
    """
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, _TRANSPORT_ERRORS):
            return exc
        exc = exc.__cause__ or exc.__context__
    return None


def _describe(exc: BaseException) -> str:
    """Beschreibt einen Transportfehler inkl. Zielhost.

    `httpx.ConnectTimeout` trägt oft **keine** Meldung (im CI-Log steht nackt
    `E httpx.ConnectTimeout`) — ohne den Host wäre die Skip-Begründung wertlos.
    """
    host = ""
    if isinstance(exc, httpx.RequestError):
        try:
            host = exc.request.url.host
        except RuntimeError:  # .request ist nicht gesetzt
            host = ""
    detail = str(exc).strip() or "(keine Meldung)"
    return f"{host or 'Upstream'}: {type(exc).__name__}: {detail}"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if report.when != "call" or not report.failed:
        return report
    if item.get_closest_marker("live") is None:
        return report
    cause = _transport_cause(call.excinfo.value if call.excinfo is not None else None)
    if cause is None:
        return report

    reason = f"Upstream nicht erreichbar — {_describe(cause)}"
    report.outcome = "skipped"
    # 3-Tupel (Datei, Zeile, Meldung): so stellt pytest einen Skip dar.
    report.longrepr = (str(item.path), item.location[1] + 1, f"Skipped: {reason}")
    item.config.stash.setdefault(_UPSTREAM_SKIPS, []).append(f"{item.nodeid} — {reason}")
    return report


def pytest_terminal_summary(terminalreporter):
    entries = terminalreporter.config.stash.get(_UPSTREAM_SKIPS, [])
    if not entries:
        return
    terminalreporter.section("Upstream nicht erreichbar (übersprungen)", sep="=", yellow=True)
    for entry in entries:
        terminalreporter.write_line(f"  ⚠️  {entry}")
    terminalreporter.write_line(
        "  Transportfehler sagen nichts über den API-Vertrag aus. Trifft es "
        "denselben Host mehrere Nächte hintereinander, ist der Dienst weg — "
        "dann untersuchen, nicht ignorieren."
    )
