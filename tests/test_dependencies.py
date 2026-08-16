#!/usr/bin/env python3
"""Die ruff-Version steht an genau einer Stelle — und bleibt dort.

Sie stand an dreien: `ruff>=0.4.0` im `[dev]`-Extra und zweimal
`pip install ruff==0.16.1` in `ci.yml`, je einmal in den Jobs `test` und
`lint`. Die CI-Schritte liefen nach dem Install und gewannen gegen pyproject,
der Wert dort war also wirkungslos. Wer die Gates lokal fuhr, bekam die
jeweils neueste Version (gemessen am 16.8.2026: 0.16.3) und damit Meldungen
ueber Code, den niemand angefasst hatte.

Beide Faelle einzeln neutralisierbar: Spanne zurueck ins Extra laesst
`test_ruff_ist_exakt_gepinnt` fallen, ein `pip install ruff` in irgendeinem
Workflow laesst `test_der_pin_ist_die_einzige_versionsquelle` fallen.
"""

from __future__ import annotations

import pathlib
import re
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"


def _dev_abhaengigkeiten() -> list[str]:
    daten = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return daten["project"]["optional-dependencies"]["dev"]


def test_ruff_ist_exakt_gepinnt() -> None:
    """Eine Spanne laesst lokalen Lauf und CI verschiedene ruff-Versionen fahren."""
    specs = [s for s in _dev_abhaengigkeiten() if re.match(r"^ruff\b", s)]
    assert len(specs) == 1, f"genau ein ruff-Specifier erwartet, gefunden: {specs}"
    assert re.fullmatch(r"ruff==\d+\.\d+\.\d+", specs[0]), (
        f"ruff muss als ruff==X.Y.Z gepinnt sein, gefunden {specs[0]!r}. "
        "Eine Spanne laesst lokal und in der CI verschiedene Versionen laufen."
    )


def test_der_pin_ist_die_einzige_versionsquelle() -> None:
    """Kein Workflow darf ruff selbst installieren.

    Ein solcher Schritt laeuft nach dem Install des Extras und ueberstimmt den
    Pin — die Zahl in pyproject waere dann Dekoration.
    """
    for workflow in sorted(_WORKFLOWS.glob("*.yml")):
        # Kommentare ausgenommen: der in ci.yml zitiert den verbotenen Befehl,
        # um zu erklaeren, warum er nicht zurueckkommen soll.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if re.search(r"pip install\s+ruff", z)]
        assert not treffer, (
            f"{workflow.name} installiert ruff direkt ({treffer}). Dieser Schritt "
            "laeuft nach dem [dev]-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_workflow_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefung oben gegen ein leeres Verzeichnis ab.

    Faende der Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = list(_WORKFLOWS.glob("*.yml"))
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )
