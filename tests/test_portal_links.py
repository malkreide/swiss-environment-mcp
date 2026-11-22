"""Live: Antworten die Portal-Links der Naturgefahren-Router noch?

`env_hazard_overview` und `env_hazard_regions` sind netzwerkfrei — sie geben
nur Links aus. Kein Unit-Test merkt, wenn ein Portal umzieht. Genau so stand
bis zum 22.11.2026 ein toter Link in der Ausgabe
(`meteoschweiz.admin.ch/wetter/warnungen.html`, HTTP 404), aufgefallen nur beim
Nachmessen.

Eingeordnet nach CLAUDE.md («Entscheidend ist, ob die Quelle überhaupt
geantwortet hat»):

- 404 / 410: die Quelle hat geantwortet, der Link ist tot -> Fehlschlag
  (im Live-Job ein `finding`, öffnet ein Issue).
- 403 / 429 / 5xx / Netzfehler: sagt über den Link nichts — etwa ein
  Bot-Schutz gegen CI-Runner -> übersprungen, mit Grund.
"""

from __future__ import annotations

import httpx
import pytest

from swiss_environment_mcp.server import _PORTAL_LINKS

pytestmark = pytest.mark.live

_LINKS = [
    pytest.param(url, id=f"{portal}-{lang}")
    for portal, links in _PORTAL_LINKS.items()
    for lang, url in links.items()
]
_DEAD = {404, 410}


@pytest.mark.parametrize("url", _LINKS)
def test_portal_link_resolves(url: str) -> None:
    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=25.0,
            headers={"User-Agent": "swiss-environment-mcp linkcheck"},
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"keine Antwort ({type(exc).__name__}) — über den Link nicht entscheidbar")
    if resp.status_code in _DEAD:
        pytest.fail(f"HTTP {resp.status_code}: Link ist tot ({resp.url})")
    if resp.status_code != 200:
        pytest.skip(f"HTTP {resp.status_code} — keine Aussage über den Link")
