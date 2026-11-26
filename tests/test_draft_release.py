"""`draft-release.yml` — Versionsprüfung und Release-Text, ausgeführt statt nachgebaut.

Der Workflow legt nur einen Entwurf an; das Veröffentlichen startet
`publish.yml`. Was hier schiefgeht, landet also im Release-Text oder im Tag,
den ein Mensch danach mit einem Klick veröffentlicht.

Die `run`-Blöcke werden mit bash ausgeführt. `gh` kommt nicht vor: geprüft
werden nur die zwei Schritte davor.

Anlass: Bis zum 26.11.2026 stand `${{ inputs.version }}` direkt im `run`-Block
der Versionsprüfung — Shell-Injektion über das Eingabefeld. Übernommen aus
`meteoswiss-mcp` (PR #90), wo der Workflow gleich mit `env` entstand.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from release_version import pyproject_version  # noqa: E402

DRAFT = ROOT / ".github" / "workflows" / "draft-release.yml"
VERSION = pyproject_version(ROOT / "pyproject.toml")


def _steps() -> list[dict]:
    return yaml.safe_load(DRAFT.read_text())["jobs"]["draft"]["steps"]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"Schritt {name!r} fehlt in draft-release.yml")


def _bash(script: str, cwd: Path, **env: str) -> subprocess.CompletedProcess:
    out = cwd / ".github_output"
    out.write_text("")
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env={"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(out), **env},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def work(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "release_version.py", repo / "scripts")
    shutil.copy(ROOT / "pyproject.toml", repo)
    return repo


def _outputs(work: Path) -> dict[str, str]:
    lines = (work / ".github_output").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if line)


# --- Version ------------------------------------------------------------------

VERSION_STEP = "Version bestimmen und gegen pyproject.toml prüfen"


def test_input_reaches_script_only_through_env():
    """${{ inputs.* }} in einem run-Block wäre Shell-Injektion über das Eingabefeld."""
    for step in _steps():
        assert "inputs." not in step.get("run", ""), step.get("name")
    assert _step(VERSION_STEP)["env"] == {"INPUT_VERSION": "${{ inputs.version }}"}


@pytest.mark.parametrize("given", ["", VERSION, f"v{VERSION}", f"V{VERSION}"])
def test_version_step_accepts_pyproject_version(work, given):
    proc = _bash(_step(VERSION_STEP)["run"], work, INPUT_VERSION=given)
    assert proc.returncode == 0, proc.stderr
    assert _outputs(work) == {"version": VERSION, "tag": f"v{VERSION}"}


@pytest.mark.parametrize("given", ["99.0.0", "vv" + VERSION, f"{VERSION}rc1"])
def test_version_step_rejects_other_versions(work, given):
    proc = _bash(_step(VERSION_STEP)["run"], work, INPUT_VERSION=given)
    assert proc.returncode != 0
    assert _outputs(work) == {}
    assert "passt nicht zu pyproject.toml" in proc.stderr


def test_version_step_injection_attempt_does_nothing(work):
    marker = work.parent / "pwned"
    proc = _bash(_step(VERSION_STEP)["run"], work, INPUT_VERSION=f"$(touch {marker})")
    assert proc.returncode != 0
    assert not marker.exists()


# --- Release-Text -------------------------------------------------------------

NOTES_STEP = "Release-Notizen aus CHANGELOG.md extrahieren"

CHANGELOG = """\
# Changelog

## [Unreleased]

## [0.8.0] - 2026-12-01

Zusammenfassung oben.

### Fixed

- Ein Punkt.

## [0.7.0] - 2026-09-27

Alter Text.
"""


def _run_notes(
    tmp_path: Path, changelog: str, version: str
) -> tuple[subprocess.CompletedProcess, str]:
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    proc = _bash(_step(NOTES_STEP)["run"], tmp_path, VERSION=version)
    notes = tmp_path / "release-notes.md"
    return proc, notes.read_text() if notes.exists() else ""


def test_notes_take_exactly_the_version_section(tmp_path):
    proc, notes = _run_notes(tmp_path, CHANGELOG, "0.8.0")
    assert proc.returncode == 0, proc.stderr
    body = notes.split("\n---\n")[0]
    assert body == "Zusammenfassung oben.\n\n### Fixed\n\n- Ein Punkt.\n"
    assert "Alter Text" not in notes


def test_notes_fail_for_missing_section(tmp_path):
    proc, _ = _run_notes(tmp_path, CHANGELOG, "0.9.0")
    assert proc.returncode != 0
    assert "Kein CHANGELOG-Abschnitt '## [0.9.0]'" in proc.stdout + proc.stderr


def test_notes_fail_for_empty_section(tmp_path):
    changelog = CHANGELOG.replace("Zusammenfassung oben.\n\n### Fixed\n\n- Ein Punkt.\n", "\n")
    proc, _ = _run_notes(tmp_path, changelog, "0.8.0")
    assert proc.returncode != 0


def test_notes_work_on_this_changelog(tmp_path):
    """Die Überschriften dieses Repos (`## [X.Y.Z] – Datum`) trägt der awk-Ausdruck."""
    proc, notes = _run_notes(tmp_path, (ROOT / "CHANGELOG.md").read_text(), "0.7.1")
    assert proc.returncode == 0, proc.stderr
    assert notes.startswith("Patch-Release über die Arbeit seit v0.7.0")
    assert "## [0.7.0]" not in notes
