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

# Der Ausloeser-Block heisst in GitHubs Augen woertlich `on`. Ihn ueber
# `yaml.safe_load` zu suchen, geht schief, und zwar in beide Richtungen:
#
#   * YAML 1.1 — und PyYAML implementiert 1.1 — liest das blanke `on:` als den
#     Boolean `True`. Auf `"on"` zu pruefen ergaebe einen Fehlalarm auf JEDEN
#     Workflow. Gemessen an `ci.yml`: die Schluessel sind `['name', True,
#     'jobs']`.
#   * Auf `True` zu pruefen ist aber genauso falsch, und das ist die
#     gefaehrliche Richtung. `true:`, `yes:` und `on:` landen alle auf
#     demselben Schluessel `True`; `1:` landet auf `1`, und `1 == True` ist in
#     Python wahr. Ein Workflow mit `true:` statt `on:` hat fuer GitHub GAR
#     KEINEN Ausloeser und laeuft nie — die Zusicherung bliebe gruen. Der Test
#     waere damit in genau dem Szenario blind, gegen das er geschrieben ist.
#     Aufgedeckt von einem Codex-Review auf PR #118 (P2).
#
# Gelesen wird deshalb die *urspruengliche Schreibweise* statt des aufgeloesten
# Werts: `yaml.compose` liefert den Knotenbaum, und dort traegt ein
# Schluessel-Skalar noch seinen Text (`'on'`, `'true'`, `'1'`).
AUSLOESER_SCHLUESSEL = "on"


def workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


def oberste_schluessel(text: str) -> list[str]:
    """Die Schluessel der obersten Ebene in ihrer geschriebenen Form.

    `yaml.safe_load` loest sie zu Python-Werten auf und macht damit `on:`,
    `true:` und `yes:` ununterscheidbar. `yaml.compose` haelt beim Knotenbaum
    an, wo jedes Schluessel-Skalar seinen Text noch traegt.
    """
    wurzel = yaml.compose(text)
    if not isinstance(wurzel, yaml.MappingNode):
        return []
    return [schluessel.value for schluessel, _ in wurzel.value]


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
    text = workflow.read_text(encoding="utf-8")
    daten = yaml.safe_load(text)

    assert isinstance(daten, dict), f"{workflow.name} enthaelt keine YAML-Abbildung: {daten!r}"
    schluessel = oberste_schluessel(text)
    assert AUSLOESER_SCHLUESSEL in schluessel, (
        f"{workflow.name} hat keinen woertlichen `on:`-Block (gefunden: {schluessel}). "
        "Ohne Ausloeser laeuft der Workflow nie — und `true:` oder `yes:` sehen "
        "nach `safe_load` genauso aus wie `on:`, deshalb die Schreibweise."
    )
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
    assert "ci.yml" in namen, (
        "der Scan findet nicht einmal ci.yml -- dann sagt er ueber die "
        "uebrigen Workflows auch nichts"
    )


@pytest.mark.parametrize("schreibweise", ["true", "yes", "1", "On", "ON"])
def test_ein_falsch_geschriebener_ausloeser_faellt_auf(schreibweise: str) -> None:
    """Das Loch, das ein Codex-Review auf PR #118 aufgedeckt hat.

    Ein Workflow mit `true:` statt `on:` ist gueltiges YAML, hat fuer GitHub
    aber GAR KEINEN Ausloeser — er laeuft nie. Genau das lautlose Verschwinden,
    gegen das diese Datei geschrieben ist. Ueber `safe_load` war es unsichtbar:
    `on`, `true` und `yes` werden alle zu `True` aufgeloest, `1` zu `1`, und
    `1 == True` ist in Python wahr.

    `On` und `ON` sind der Vollstaendigkeit halber dabei: YAML 1.1 loest auch
    sie zum Boolean auf, GitHub verlangt aber die Kleinschreibung.
    """
    kaputt = f"{schreibweise}:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-latest\n"

    assert AUSLOESER_SCHLUESSEL not in oberste_schluessel(kaputt), (
        f"`{schreibweise}:` wird als gueltiger Ausloeser durchgewunken — "
        "der Test ist blind fuer einen Workflow, der nie laeuft"
    )


def test_der_echte_ausloeser_wird_erkannt() -> None:
    """Positivkontrolle zur Tabelle oben: Der Pruefer darf nicht alles ablehnen,
    sonst faerbte er jeden heilen Workflow rot."""
    heil = "on:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-latest\n"

    assert AUSLOESER_SCHLUESSEL in oberste_schluessel(heil)


def test_safe_load_wuerde_die_falschschreibung_nicht_sehen() -> None:
    """Warum `oberste_schluessel` ueberhaupt existiert — als Messung, nicht als
    Behauptung. Faellt dieser Test, loest PyYAML `on:` nicht mehr zum Boolean
    auf; dann ist die Umleitung ueber `yaml.compose` neu zu bewerten."""
    per_on = yaml.safe_load("on:\n  push:\n")
    per_true = yaml.safe_load("true:\n  push:\n")

    assert list(per_on) == list(per_true) == [True], (
        "PyYAML unterscheidet `on:` und `true:` jetzt — die Umleitung ueber "
        "den Knotenbaum ist neu zu bewerten"
    )
