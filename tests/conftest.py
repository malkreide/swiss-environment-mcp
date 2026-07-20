"""Gemeinsame Test-Fixtures für alle Test-Module.

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
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp import api_client as _api


@pytest.fixture(autouse=True)
async def _reset_shared_http_client():
    """Frischer geteilter AsyncClient je Test, sauber auf dem eigenen Loop geschlossen."""
    await _api.shutdown()
    yield
    await _api.shutdown()
