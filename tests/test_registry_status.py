"""Registry-Status einer Version setzen — Eingabeprüfung und Workflow-Job.

Anlass: der fehlerhafte Registry-Eintrag `V0.7.1` (22.11.2026). Löschen lässt
er sich nicht; `mcp-publisher status --status deleted` versteckt ihn.

Die Schritte des Jobs `registry-status` in `publish.yml` werden mit bash
ausgeführt, nicht nachgebaut. `mcp-publisher` und `sleep` sind dabei durch
Attrappen ersetzt — veröffentlicht wird nichts.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from registry_status_args import check, pyproject_version  # noqa: E402

PUBLISH = ROOT / ".github" / "workflows" / "publish.yml"
SERVER = json.loads((ROOT / "server.json").read_text())["name"]
CURRENT = pyproject_version(ROOT / "pyproject.toml")


# --- Eingabeprüfung -------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "status"),
    [("V0.7.1", "deleted"), ("V0.7.1", "deprecated"), ("V0.7.1", "active"), ("0.6.0", "deleted")],
)
def test_allowed_changes(version, status):
    check(version, status, CURRENT)


def test_current_version_cannot_be_hidden():
    """Ein Vertipper V0.7.1 → 0.7.1 darf die gültige Version nicht verstecken."""
    for status in ("deleted", "deprecated"):
        with pytest.raises(ValueError, match="aktuelle Version"):
            check(CURRENT, status, CURRENT)
    check(CURRENT, "active", CURRENT)  # zurück auf active ist erlaubt


@pytest.mark.parametrize("version", ["", "V0.7.1;touch x", "V0.7.1 ", "../0.7.0", "V0.7.1$(id)"])
def test_unsafe_version_strings_are_rejected(version):
    with pytest.raises(ValueError, match="unzulässigen Zeichen"):
        check(version, "deleted", CURRENT)


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError, match="unbekannt"):
        check("V0.7.1", "purge", CURRENT)


# --- Workflow-Struktur --------------------------------------------------------


def _workflow() -> dict:
    return yaml.safe_load(PUBLISH.read_text())


def _dispatch_inputs() -> dict:
    """Die Eingaben von workflow_dispatch (safe_load macht aus `on` ein True)."""
    return _workflow()[True]["workflow_dispatch"]["inputs"]


def _job(name: str) -> dict:
    return _workflow()["jobs"][name]


def _step(job: str, name: str) -> dict:
    for step in _job(job)["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"Schritt {name!r} fehlt in Job {job!r}")


def test_manual_default_stays_publish():
    """Ohne Auswahl tut der Handstart dasselbe wie vor dieser Änderung."""
    inputs = _dispatch_inputs()
    assert inputs["action"]["default"] == "publish"
    assert inputs["action"]["options"] == ["publish", "set-status"]
    assert inputs["status"]["options"] == ["deleted", "deprecated", "active"]


def test_registry_publish_only_for_action_publish():
    cond = " ".join(_job("publish-mcp")["if"].split())
    assert "inputs.action == 'publish'" in cond


def test_status_job_only_for_set_status():
    assert _job("registry-status")["if"] == (
        "github.event_name == 'workflow_dispatch' && inputs.action == 'set-status'"
    )


def test_no_step_ever_targets_all_versions():
    for name, job in _workflow()["jobs"].items():
        for step in job["steps"]:
            assert "--all-versions" not in step.get("run", ""), (name, step.get("name"))


def test_inputs_never_interpolated_into_scripts():
    """${{ inputs.* }} in einem run-Block wäre Shell-Injektion über ein Eingabefeld."""
    for name, job in _workflow()["jobs"].items():
        for step in job["steps"]:
            assert "inputs." not in step.get("run", ""), (name, step.get("name"))
    env = _job("registry-status")["env"]
    assert env == {
        "VERSION": "${{ inputs.version }}",
        "STATUS": "${{ inputs.status }}",
        "MESSAGE": "${{ inputs.message }}",
    }


# --- Schritte ausführen -------------------------------------------------------


def _bash(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], cwd=cwd, env=env, capture_output=True, text=True)


@pytest.fixture
def work(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "registry_status_args.py", repo / "scripts")
    shutil.copy(ROOT / "pyproject.toml", repo)
    shutil.copy(ROOT / "server.json", repo)
    return repo


def _run_check(work: Path, **env: str) -> tuple[int, dict[str, str], str]:
    out = work.parent / "github_output"
    out.write_text("")
    proc = _bash(
        _step("registry-status", "Eingaben prüfen")["run"],
        work,
        {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(out), **env},
    )
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines() if line)
    return proc.returncode, outputs, proc.stdout + proc.stderr


def test_check_step_on_main(work):
    code, outputs, _ = _run_check(
        work, GITHUB_REF="refs/heads/main", VERSION="V0.7.1", STATUS="deleted"
    )
    assert code == 0
    assert outputs["server"] == SERVER
    assert outputs["url"] == (
        "https://registry.modelcontextprotocol.io/v0/servers/"
        "io.github.malkreide%2Fswiss-environment-mcp/versions/V0.7.1?include_deleted=true"
    )


def test_check_step_refuses_other_branch(work):
    code, outputs, log = _run_check(
        work, GITHUB_REF="refs/heads/feature", VERSION="V0.7.1", STATUS="deleted"
    )
    assert code != 0 and outputs == {}
    assert "nur von main" in log


def test_check_step_refuses_hiding_current_version(work):
    code, outputs, log = _run_check(
        work, GITHUB_REF="refs/heads/main", VERSION=CURRENT, STATUS="deleted"
    )
    assert code != 0 and outputs == {}
    assert "aktuelle Version" in log


def test_check_step_injection_attempt_does_nothing(work):
    marker = work.parent / "pwned"
    code, outputs, _ = _run_check(
        work, GITHUB_REF="refs/heads/main", VERSION=f"V0.7.1;touch {marker}", STATUS="deleted"
    )
    assert code != 0 and outputs == {}
    assert not marker.exists()


def _fake(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run_set(work: Path, **env: str) -> list[str]:
    """«Status setzen» mit einer mcp-publisher-Attrappe, die ihre Argumente notiert."""
    argfile = work.parent / "args"
    _fake(work, "mcp-publisher", f'printf "%s\\n" "$@" > "{argfile}"')
    proc = _bash(
        _step("registry-status", "Status setzen")["run"],
        work,
        {"PATH": os.environ["PATH"], "SERVER": SERVER, "MESSAGE": "", **env},
    )
    assert proc.returncode == 0, proc.stderr
    return argfile.read_text().splitlines()


def test_set_step_passes_exact_arguments(work):
    args = _run_set(work, VERSION="V0.7.1", STATUS="deleted", MESSAGE="Tippfehler im Tag")
    assert args == [
        "status",
        "--status",
        "deleted",
        "--message",
        "Tippfehler im Tag",
        SERVER,
        "V0.7.1",
    ]


def test_set_step_drops_message_for_active(work):
    """Die CLI erlaubt --message bei active nicht."""
    args = _run_set(work, VERSION="V0.7.1", STATUS="active", MESSAGE="egal")
    assert args == ["status", "--status", "active", SERVER, "V0.7.1"]


def test_set_step_without_message(work):
    args = _run_set(work, VERSION="V0.7.1", STATUS="deleted")
    assert args == ["status", "--status", "deleted", SERVER, "V0.7.1"]


def _run_verify(tmp_path: Path, registry_status: str, wanted: str) -> subprocess.CompletedProcess:
    """«Ergebnis prüfen» gegen eine lokale Antwort (file://), sleep als Attrappe."""
    answer = tmp_path / "entry.json"
    meta = {"io.modelcontextprotocol.registry/official": {"status": registry_status}}
    answer.write_text(json.dumps({"_meta": meta}))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fake(bindir, "sleep", "exit 0")
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "URL": answer.as_uri(),
        "STATUS": wanted,
        "VERSION": "V0.7.1",
    }
    return _bash(_step("registry-status", "Ergebnis in der Registry prüfen")["run"], tmp_path, env)


def test_verify_step_accepts_matching_status(tmp_path):
    assert _run_verify(tmp_path, "deleted", "deleted").returncode == 0


def test_verify_step_fails_when_registry_disagrees(tmp_path):
    proc = _run_verify(tmp_path, "active", "deleted")
    assert proc.returncode != 0
    assert "weiterhin 'active' statt 'deleted'" in proc.stdout + proc.stderr
