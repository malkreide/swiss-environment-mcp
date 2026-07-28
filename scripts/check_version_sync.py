"""
Versions-Synchronität zwischen `pyproject.toml` und `server.json` prüfen.

Hintergrund: `server.json` ist das MCP-Registry-Manifest. Beim Release
synchronisiert `publish.yml` dessen Version zur Laufzeit aus dem Tag-Namen —
die *committete* Version wirkt also nie auf das publizierte Artefakt. Genau
deshalb fiel nicht auf, dass die Datei von v0.2.3 bis v0.5.0 auf einer
veralteten Version stand: funktional folgenlos, beim Lesen aber irreführend.

Dieser Check schliesst die Lücke: er hält die committete Datei ehrlich, ohne
am Release-Mechanismus etwas zu ändern.

Verwendung:
    python scripts/check_version_sync.py     # exit 1 bei Abweichung

Bewusst nur Standardbibliothek (`tomllib` ab Python 3.11, `requires-python`
dieses Projekts ist >=3.11) — der Check läuft damit auch im schlanken
lint-Job der CI ohne Projekt-Installation.
"""

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"


def main() -> None:
    pyproject_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    server = json.loads(SERVER_JSON.read_text(encoding="utf-8"))

    # Beide Stellen prüfen: das Server-Objekt und jeden Package-Eintrag. Ein
    # Bump nur an einer der beiden wäre sonst unentdeckt geblieben.
    found: list[tuple[str, str]] = [("server.json → version", server.get("version", ""))]
    for i, pkg in enumerate(server.get("packages", [])):
        found.append((f"server.json → packages[{i}].version", pkg.get("version", "")))

    mismatches = [(where, value) for where, value in found if value != pyproject_version]
    if mismatches:
        print(
            f"DRIFT: pyproject.toml steht auf {pyproject_version!r}, "
            "server.json weicht ab:",
            file=sys.stderr,
        )
        for where, value in mismatches:
            print(f"  {where} = {value!r}", file=sys.stderr)
        print(
            "\nBeide Dateien im selben Commit bumpen (siehe CONTRIBUTING, Abschnitt "
            "«Releases»). Hinweis: publish.yml überschreibt server.json beim "
            "Veröffentlichen ohnehin aus dem Tag — die committete Version bleibt "
            "trotzdem die, die Menschen lesen.",
            file=sys.stderr,
        )
        sys.exit(1)

    checked = ", ".join(where.split("→ ")[1] for where, _ in found)
    print(f"Versions-Sync OK ({pyproject_version}; geprüft: {checked})")


if __name__ == "__main__":
    main()
