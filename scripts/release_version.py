"""
Die Version, die `publish.yml` veröffentlichen darf — oder ein Abbruch.

`pyproject.toml` ist die einzige Quelle der Wahrheit (siehe
`check_version_sync.py`). Bis v0.7.1 nahm `publish.yml` die Version stattdessen
aus dem Tag-Namen und entfernte dabei nur ein kleines `v`
(`${GITHUB_REF_NAME#v}`). Am 22.11.2026 hiess der Tag `V0.7.1`: PyPI bekam
korrekt `0.7.1` (aus `pyproject.toml`), die MCP Registry aber einen Eintrag
`V0.7.1` — keine Semver-Version, deshalb nie als «latest» markiert. Clients
sahen dort weiter 0.7.0.

Regeln:

  - Mit `--tag`: genau ein führendes `v` oder `V` wird entfernt; der Rest muss
    **exakt** der Version aus `pyproject.toml` entsprechen. Ein abweichender Tag
    bricht ab, bevor irgendetwas veröffentlicht ist.
  - Ohne `--tag` (manueller Start nur des Registry-Jobs): die Version aus
    `pyproject.toml`.
  - Die Version muss `X.Y.Z` sein. Die Registry markiert nur Semver als
    «latest»; alles andere wäre ein Eintrag, den kein Client als neuesten sieht.

Ausgabe: die Version auf stdout. Fehler: `::error::…` auf stderr, Exit 1.

Verwendung:
    python scripts/release_version.py --tag "$GITHUB_REF_NAME"
    python scripts/release_version.py
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

SEMVER = re.compile(r"\d+\.\d+\.\d+")


def pyproject_version(path: Path) -> str:
    with path.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def release_version(pyproject: str, tag: str | None) -> str:
    """Gibt die zu veröffentlichende Version zurück oder wirft ValueError."""
    if not SEMVER.fullmatch(pyproject):
        raise ValueError(
            f"pyproject.toml-Version {pyproject!r} ist kein X.Y.Z — die MCP Registry "
            "würde sie nie als «latest» führen."
        )
    if tag is None:
        return pyproject
    stripped = tag[1:] if tag[:1] in ("v", "V") else tag
    if stripped != pyproject:
        raise ValueError(
            f"Tag {tag!r} passt nicht zu pyproject.toml ({pyproject!r}). Erwartet: "
            f"'v{pyproject}'. Erst die Version bumpen oder den Tag korrigieren."
        )
    return pyproject


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--tag", help="Release-Tag, z.B. v0.7.1")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)
    try:
        version = release_version(pyproject_version(args.pyproject), args.tag)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
