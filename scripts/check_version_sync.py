"""
Versions-Synchronität zwischen `pyproject.toml` und `server.json` prüfen —
und sicherstellen, dass in `src/` keine Version von Hand gepflegt wird.

Hintergrund: `server.json` ist das MCP-Registry-Manifest. Beim Release
synchronisiert `publish.yml` dessen Version zur Laufzeit aus dem Tag-Namen —
die *committete* Version wirkt also nie auf das publizierte Artefakt. Genau
deshalb fiel nicht auf, dass die Datei von v0.2.3 bis v0.5.0 auf einer
veralteten Version stand: funktional folgenlos, beim Lesen aber irreführend.

Dieser Check schliesst die Lücke: er hält die committete Datei ehrlich, ohne
am Release-Mechanismus etwas zu ändern.

Zweiter Teil (seit dem Umbau des User-Agents auf `importlib.metadata`): in
`src/` darf überhaupt keine Versionsnummer mehr stehen. Der Laufzeit-Wert
kommt aus den Paket-Metadaten; ein wieder eingefügtes Literal wäre der Beginn
derselben Drift, die den User-Agent von v0.2.0 bis v0.5.0 falsch melden liess.

Verwendung:
    python scripts/check_version_sync.py     # exit 1 bei Abweichung

Bewusst nur Standardbibliothek (`tomllib` ab Python 3.11, `requires-python`
dieses Projekts ist >=3.11) — der Check läuft damit auch im schlanken
lint-Job der CI ohne Projekt-Installation.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"
SRC = ROOT / "src"
READMES = ("README.md", "README.de.md")

# Shields.io-Badge im README: ![Version](https://img.shields.io/badge/version-X.Y.Z-blue)
_BADGE = re.compile(r"img\.shields\.io/badge/version-([^-\s)]+)-")

# Ein von Hand gepflegter Versionsstring in `src/`. Beide Formen, die es hier
# tatsächlich gab: der User-Agent (`swiss-environment-mcp/0.5.1`) und das
# Dunder in `__init__.py`. Gesucht wird jeweils eine gepunktete Zahl —
# das trennt echte Versionen sowohl von der GitHub-URL im User-Agent als auch
# vom Fallback `"0+unknown"`, der ja gerade *keine* Version behauptet.
_HARDCODED = re.compile(r"""swiss-environment-mcp/\d+\.\d|__version__\s*=\s*["']\d+\.\d""")


def check_no_hardcoded_version() -> list[tuple[str, int, str]]:
    """Findet manuell gepflegte Versionsnummern in `src/`."""
    hits: list[tuple[str, int, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _HARDCODED.search(line):
                hits.append((str(path.relative_to(ROOT)), lineno, line.strip()))
    return hits


def main() -> None:
    pyproject_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    server = json.loads(SERVER_JSON.read_text(encoding="utf-8"))

    # Beide Stellen prüfen: das Server-Objekt und jeden Package-Eintrag. Ein
    # Bump nur an einer der beiden wäre sonst unentdeckt geblieben.
    found: list[tuple[str, str]] = [("server.json → version", server.get("version", ""))]
    for i, pkg in enumerate(server.get("packages", [])):
        found.append((f"server.json → packages[{i}].version", pkg.get("version", "")))

    # Die Versions-Badges der READMEs. Rein kosmetisch, aber dieselbe
    # Drift-Klasse: nichts erzwingt sie, also bleiben sie beim Bump stehen.
    for name in READMES:
        path = ROOT / name
        if not path.exists():
            continue
        for match in _BADGE.finditer(path.read_text(encoding="utf-8")):
            found.append((f"{name} → Versions-Badge", match.group(1)))

    mismatches = [(where, value) for where, value in found if value != pyproject_version]
    if mismatches:
        print(
            f"DRIFT: pyproject.toml steht auf {pyproject_version!r}, "
            "folgende Stellen weichen ab:",
            file=sys.stderr,
        )
        for where, value in mismatches:
            print(f"  {where} = {value!r}", file=sys.stderr)
        print(
            "\nAlle Stellen im selben Commit bumpen (siehe CONTRIBUTING, Abschnitt "
            "«Releases»). Hinweis: publish.yml überschreibt server.json beim "
            "Veröffentlichen ohnehin aus dem Tag — die committete Version bleibt "
            "trotzdem die, die Menschen lesen.",
            file=sys.stderr,
        )
        sys.exit(1)

    hardcoded = check_no_hardcoded_version()
    if hardcoded:
        print("HARDCODED: Versionsnummer in src/ gefunden:", file=sys.stderr)
        for path, lineno, line in hardcoded:
            print(f"  {path}:{lineno}: {line}", file=sys.stderr)
        print(
            "\nDie Laufzeit-Version kommt aus den Paket-Metadaten "
            "(`swiss_environment_mcp.__version__`, gespeist aus "
            "importlib.metadata). Statt eines Literals von dort lesen — "
            "sonst beginnt dieselbe Drift von vorn.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Volle Bezeichnung statt nur des Feldnamens — sonst stünde für die beiden
    # READMEs zweimal dasselbe «Versions-Badge» da.
    checked = ", ".join(where for where, _ in found)
    print(
        f"Versions-Sync OK ({pyproject_version}; geprüft: {checked}; "
        "keine hartkodierte Version in src/)"
    )


if __name__ == "__main__":
    main()
