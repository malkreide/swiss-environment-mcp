"""
LINDAS-Zugriffsmodul (Linked Data Service des Bundes, lindas.admin.ch).

ARCHITEKTUR-NOTIZ: Dieses Modul ist bewusst **extraktionsfähig** gebaut und
wird nach `lindas-mcp` gehoben, sobald ein zweiter Server LINDAS nutzt
(Kandidat: `wsl-envidat-mcp`). Drei-Schichten-Trennung:

  - `client.py`  kennt nur SPARQL und HTTP (Transport, Retry, Fehlerklassen).
  - `cube.py`    kennt das cube.link-Vokabular (Zwei-Phasen-Zugriff,
                 Versions-Deduplizierung, Code→Label-Auflösung, Lizenz).
  - Die Environment-Tools kennen nur `cube.py`, nie den rohen Client.

Kein Modul-Teil nimmt freies SPARQL von Tool-Aufrufern entgegen — freies
SPARQL bleibt intern (Guardrail gegen Query-Injection und Blind-Scans, die
auf LINDAS in 70–90-s-Timeouts laufen; siehe docs/probe-lindas-hydro.md).
"""

from . import client, cube

__all__ = ["client", "cube"]
