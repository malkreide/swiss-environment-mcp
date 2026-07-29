"""Swiss Environment MCP – BAFU-Daten für Luft, Wasser und Naturgefahren."""

from importlib.metadata import PackageNotFoundError, version

#: Distributionsname aus `pyproject.toml` — der Schlüssel, unter dem die
#: installierten Metadaten liegen.
DIST_NAME = "swiss-environment-mcp"

try:
    __version__ = version(DIST_NAME)
except PackageNotFoundError:  # pragma: no cover - nur ohne Installation
    # Quell-Checkout ohne `pip install`. Bewusst kein plausibel aussehender
    # Platzhalter: eine erfundene Nummer wäre genau die Drift, die dieser
    # Ansatz beseitigt. "0+unknown" ist als «unbekannt» erkennbar.
    __version__ = "0+unknown"

#: User-Agent für alle ausgehenden Upstream-Requests. Zentral hier, damit der
#: Versionsstring nur an einer Stelle entsteht — und zwar aus den
#: Paket-Metadaten statt von Hand gepflegt (bis v0.5.1 hing er dreimal
#: nachweislich auf einer veralteten Version fest).
USER_AGENT = f"{DIST_NAME}/{__version__} (https://github.com/malkreide/swiss-environment-mcp)"

__all__ = ["DIST_NAME", "USER_AGENT", "__version__"]
