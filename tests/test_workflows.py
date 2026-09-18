"""Die Workflow-Dateien muessen parsen — sonst verschwindet ein Gate lautlos.

Der Anlass, datiert: Am 18.9.2026 bekam der Gate-Job in `codex-gate.yml` einen
neuen Namen, und zwar so:

    name: codex-gate: Status setzen

Das ist ungueltiges YAML — ein unquotierter Skalar mit «: » darin. Aufgefallen
ist es nur, weil die Datei von Hand gegen einen Parser gehalten wurde. Im Repo
prueft das bis dahin nichts: `test_dependencies.py` liest die Workflows als
**Text** und haette den Fehler nie gesehen.

Und das ist die unangenehme Haelfte: **Ein Workflow, der nicht parst, wird
nicht rot — er faellt aus.** GitHub startet ihn gar nicht erst, es entsteht kein
Check-Run, und in der Liste des PR fehlt er einfach. `codex-gate` waere damit
still verschwunden, und nach Teil 1 von `CLAUDE.md` sieht ein PR ohne Check
zuerst nach einem Merge-Konflikt aus — man sucht also an der falschen Stelle.
Ein rotes Gate schreit; ein abwesendes ist bloss leise.

Deshalb ist die Zusicherung hier ein eigener Test und kein Nebenprodukt: Sie
haengt nicht daran, dass irgendein anderer Test zufaellig YAML laedt.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# YAML 1.1 — und PyYAML implementiert 1.1 — liest das blanke `on:` als den
# Boolean `True`, nicht als den String `"on"`. Gemessen an `ci.yml`: die
# Schluessel der obersten Ebene sind `['name', True, 'jobs']`.
#
# Wer hier `"on"` schreibt, baut sich einen Fehlalarm auf JEDEN Workflow ein —
# also genau die Sorte Fehlbefund, gegen die diese Datei geschrieben ist. In
# YAML 1.2 waere es der String; verhaelt sich PyYAML eines Tages so, faellt
# `test_der_ausloeser_schluessel_ist_der_boolean_nicht_der_string` und sagt es.
AUSLOESER_SCHLUESSEL = True


def workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


def parse_fehler(text: str) -> str | None:
    """Die Meldung, wenn `text` kein gueltiges YAML ist — sonst `None`.

    Eigene Funktion, damit sie unten gegen bekannt kaputte Schnipsel gehalten
    werden kann. Ein Pruefer, der nur ueber die echten (heilen) Dateien laeuft,
    kann nicht zeigen, dass er ueberhaupt etwas ablehnt.
    """
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as fehler:
        return str(fehler)
    return None


# --- Die eigentliche Zusicherung ---------------------------------------------


@pytest.mark.parametrize("workflow", workflow_dateien(), ids=lambda p: p.name)
def test_jeder_workflow_ist_gueltiges_yaml(workflow: pathlib.Path) -> None:
    """Je Datei ein Testfall, nicht eine Schleife ueber alle.

    Eine Schleife meldet die erste kaputte Datei und schweigt ueber den Rest;
    bei einem Fund will man aber wissen, ob es eine ist oder alle.
    """
    fehler = parse_fehler(workflow.read_text(encoding="utf-8"))
    assert fehler is None, (
        f"{workflow.name} ist kein gueltiges YAML: {fehler}\n\n"
        "GitHub startet einen solchen Workflow nicht — er wird nicht rot, er "
        "faellt aus. Ein Gate verschwindet damit lautlos aus der Checkliste."
    )


@pytest.mark.parametrize("workflow", workflow_dateien(), ids=lambda p: p.name)
def test_jeder_workflow_hat_ausloeser_und_jobs(workflow: pathlib.Path) -> None:
    """«Parst» allein ist zu wenig — eine leere Datei parst auch.

    Ohne diese Zusicherung bliebe der Test oben gruen, wenn jemand eine Datei
    versehentlich leert: `yaml.safe_load("")` ist `None` und wirft nichts.
    """
    daten = yaml.safe_load(workflow.read_text(encoding="utf-8"))

    assert isinstance(daten, dict), f"{workflow.name} enthaelt keine YAML-Abbildung: {daten!r}"
    assert AUSLOESER_SCHLUESSEL in daten, f"{workflow.name} hat keinen `on:`-Block"
    assert daten.get("jobs"), f"{workflow.name} hat keine Jobs"


# --- Gegenprobe: lehnt der Pruefer ueberhaupt etwas ab? ----------------------


def test_der_pruefer_faellt_auf_genau_dem_fehler_der_ihn_ausgeloest_hat() -> None:
    """Der Schnipsel vom 18.9.2026, woertlich.

    Ohne diesen Fall waere `test_jeder_workflow_ist_gueltiges_yaml` eine
    Zusicherung, die noch nie etwas abgelehnt hat — gruen, weil im Repo gerade
    nichts kaputt ist, nicht weil sie prueft. Die echten Dateien lassen sich
    dafuer nicht beschaedigen; also steht der Fehler hier als Literal.
    """
    kaputt = "jobs:\n  gate:\n    name: codex-gate: Status setzen\n"

    assert parse_fehler(kaputt) is not None, (
        "der Pruefer haelt einen unquotierten Skalar mit «: » fuer gueltig — "
        "dann sagt er ueber die echten Workflows auch nichts"
    )
    # Und die Fassung, die tatsaechlich ausgeliefert wurde, muss durchgehen.
    assert parse_fehler('jobs:\n  gate:\n    name: "codex-gate: Status setzen"\n') is None


@pytest.mark.parametrize(
    "kaputt",
    [
        pytest.param("a: [1, 2\n", id="klammer-nicht-geschlossen"),
        pytest.param("a: b\n  c: d\n", id="einrueckung-springt"),
        pytest.param("a: 'unbeendet\n", id="anfuehrungszeichen-offen"),
        pytest.param("a: 1\na: 2\n" * 0 + "x: :\n", id="wert-beginnt-mit-doppelpunkt"),
    ],
)
def test_der_pruefer_lehnt_die_gaengigen_schreibfehler_ab(kaputt: str) -> None:
    """Dieselbe Absicht wie oben, breiter — nach dem Vorbild der Tabelle in
    `test_dependencies.py`: Ein Erkenner ist nur so gut wie das, was er kennt."""
    assert parse_fehler(kaputt) is not None, f"unbemerkt durchgelassen: {kaputt!r}"


def test_der_pruefer_laesst_gueltiges_yaml_durch() -> None:
    """Die Positivkontrolle zur Tabelle oben.

    Ein Pruefer, der ALLES ablehnt, bestuende sie ebenfalls — und faerbte dann
    jeden heilen Workflow rot.
    """
    heil = "name: CI\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"

    assert parse_fehler(heil) is None


# --- Absicherungen des Scans selbst ------------------------------------------


def test_der_scan_findet_die_workflows_ueberhaupt() -> None:
    """Faende der Glob nichts, waere die Parametrisierung leer — und die Datei
    gruen, ohne eine einzige Zeile YAML gelesen zu haben."""
    gefunden = workflow_dateien()

    assert len(gefunden) >= 5, f"Workflow-Scan findet fast nichts: {gefunden}"
    namen = {p.name for p in gefunden}
    assert "codex-gate.yml" in namen, (
        "der Workflow, dessen Ausfall diese Datei ausgeloest hat, ist nicht im Scan"
    )


def test_der_ausloeser_schluessel_ist_der_boolean_nicht_der_string() -> None:
    """Sagt, wann die Konstante oben wieder verschwinden darf.

    Wechselt PyYAML auf YAML 1.2, ist `on` wieder ein String; dann faellt dieser
    Test, und `AUSLOESER_SCHLUESSEL` ist auf `"on"` zu setzen — statt dass die
    Zusicherung daran still vorbeiliefe.
    """
    daten = yaml.safe_load("on:\n  push:\n")

    assert AUSLOESER_SCHLUESSEL in daten
    assert "on" not in daten, (
        "PyYAML liest `on:` jetzt als String — AUSLOESER_SCHLUESSEL nachziehen"
    )
