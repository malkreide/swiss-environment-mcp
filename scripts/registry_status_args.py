"""
Eingaben prüfen, bevor `publish.yml` den Registry-Status einer Version setzt.

Anlass: Der Tag `V0.7.1` erzeugte am 22.11.2026 einen fehlerhaften
Registry-Eintrag `V0.7.1` neben dem korrekten `0.7.1`. Löschen lässt sich ein
Eintrag in der MCP Registry nicht («Server metadata is never permanently
removed»); `mcp-publisher status --status deleted` versteckt ihn aus den
Standardlisten und ist mit `--status active` umkehrbar.

Sperren:

  - `status` nur `deleted`, `deprecated` oder `active`.
  - `version` nur aus `A-Z a-z 0-9 . _ + -` — der Wert landet in einer URL und
    als Argument eines Befehls.
  - Die **aktuelle** Version aus `pyproject.toml` darf nicht versteckt werden
    (`deleted`/`deprecated`). Ein Vertipper bei `V0.7.1` → `0.7.1` würde sonst
    die gültige neueste Version aus der Registry nehmen. Zurück auf `active`
    darf sie.

Ausgabe: nichts bei Erfolg. Fehler: `::error::…` auf stderr, Exit 1.

Verwendung:
    python scripts/registry_status_args.py --version V0.7.1 --status deleted
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

STATUSES = ("deleted", "deprecated", "active")
VERSION_CHARS = re.compile(r"[A-Za-z0-9._+-]+")


def pyproject_version(path: Path) -> str:
    with path.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def check(version: str, status: str, current: str) -> None:
    """Wirft ValueError, wenn die Statusänderung nicht zulässig ist."""
    if status not in STATUSES:
        raise ValueError(f"Status {status!r} unbekannt. Erlaubt: {', '.join(STATUSES)}.")
    if not VERSION_CHARS.fullmatch(version):
        raise ValueError(
            f"Version {version!r} leer oder mit unzulässigen Zeichen "
            "(erlaubt: Buchstaben, Ziffern, . _ + -)."
        )
    if version == current and status != "active":
        raise ValueError(
            f"{version} ist die aktuelle Version aus pyproject.toml — sie wird nicht "
            f"auf {status!r} gesetzt. Vertippt? Gemeint war vielleicht 'V{version}'."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--version", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)
    try:
        check(args.version, args.status, pyproject_version(args.pyproject))
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
