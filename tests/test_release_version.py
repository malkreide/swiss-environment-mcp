"""Die Version, die `publish.yml` veröffentlicht — Skript und Workflow.

Anlass: Der Tag `V0.7.1` (grosses V) ergab am 22.11.2026 einen
Registry-Eintrag `V0.7.1`, weil `publish.yml` nur `${GITHUB_REF_NAME#v}`
rechnete. PyPI bekam korrekt 0.7.1, die Registry führte weiter 0.7.0 als
«latest».

Getestet werden zwei Ebenen: `scripts/release_version.py` direkt und der
`run`-Block «Version bestimmen» aus `publish.yml` selbst — ausgeführt mit
bash, nicht nachgebaut.
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

from release_version import main, pyproject_version, release_version  # noqa: E402

PUBLISH = ROOT / ".github" / "workflows" / "publish.yml"


# --- Skript -----------------------------------------------------------------


@pytest.mark.parametrize("tag", ["v0.7.1", "V0.7.1", "0.7.1"])
def test_tag_matching_pyproject_is_accepted(tag):
    assert release_version("0.7.1", tag) == "0.7.1"


@pytest.mark.parametrize("tag", ["v0.7.2", "V0.7.0", "vv0.7.1", "v0.7.1 ", "release-0.7.1"])
def test_tag_not_matching_pyproject_is_rejected(tag):
    with pytest.raises(ValueError, match="passt nicht zu pyproject.toml"):
        release_version("0.7.1", tag)


def test_without_tag_the_pyproject_version_is_used():
    assert release_version("0.7.1", None) == "0.7.1"


@pytest.mark.parametrize("version", ["0.7.1rc1", "0.7", "V0.7.1"])
def test_non_semver_pyproject_version_is_rejected(version):
    """Die Registry markiert nur X.Y.Z als «latest»."""
    with pytest.raises(ValueError, match="kein X.Y.Z"):
        release_version(version, None)


def test_main_reports_error_and_exit_code(capsys, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\n')
    assert main(["--pyproject", str(pyproject), "--tag", "V1.2.3"]) == 0
    assert capsys.readouterr().out.strip() == "1.2.3"
    assert main(["--pyproject", str(pyproject), "--tag", "v9.9.9"]) == 1
    assert "::error::" in capsys.readouterr().err


def test_repo_pyproject_version_is_semver():
    """Die echte Version muss den Release-Pfad passieren können."""
    version = pyproject_version(ROOT / "pyproject.toml")
    assert release_version(version, f"v{version}") == version


# --- Workflow -----------------------------------------------------------------


def _workflow() -> dict:
    return yaml.safe_load(PUBLISH.read_text())


def _triggers() -> list[str]:
    """Auslöser in geschriebener Form (safe_load macht aus `on` ein True)."""
    root = yaml.compose(PUBLISH.read_text())
    for key, value in root.value:
        if key.value == "on":
            return [k.value for k, _ in value.value]
    raise AssertionError("publish.yml hat keinen on:-Block")


def _step(job: str, name: str) -> dict:
    for step in _workflow()["jobs"][job]["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"Schritt {name!r} fehlt in Job {job!r}")


def test_tag_is_no_longer_used_as_version():
    """In keinem ausgeführten Schritt — der Kommentar oben darf ihn zitieren."""
    for name, job in _workflow()["jobs"].items():
        for step in job["steps"]:
            assert "GITHUB_REF_NAME#" not in step.get("run", ""), (name, step.get("name"))


def test_triggers_are_release_and_manual():
    assert _triggers() == ["release", "workflow_dispatch"]


def test_build_checks_tag_before_building():
    names = [s.get("name") for s in _workflow()["jobs"]["build"]["steps"]]
    check = names.index("Tag gegen pyproject.toml prüfen")
    assert check < names.index("Build package")
    assert "release_version.py --tag" in _step("build", "Tag gegen pyproject.toml prüfen")["run"]


@pytest.mark.parametrize("job", ["build", "publish"])
def test_build_and_pypi_only_run_on_release(job):
    assert _workflow()["jobs"][job]["if"] == "github.event_name == 'release'"


def test_registry_job_condition():
    cond = " ".join(_workflow()["jobs"]["publish-mcp"]["if"].split())
    assert "github.event_name == 'release' && needs.publish.result == 'success'" in cond
    assert (
        "github.event_name == 'workflow_dispatch' && inputs.action == 'publish' && "
        "needs.publish.result == 'skipped'"
    ) in cond


def test_manual_run_checks_pypi_before_publishing():
    step = _step("publish-mcp", "Version muss auf PyPI liegen (nur manuell)")
    assert step["if"] == "github.event_name == 'workflow_dispatch'"
    names = [s.get("name") for s in _workflow()["jobs"]["publish-mcp"]["steps"]]
    assert names.index(step["name"]) < names.index("Publish server to MCP Registry")


def _run_version_step(tmp_path: Path, **env: str) -> tuple[int, str, str]:
    """Den echten run-Block «Version bestimmen» mit bash ausführen."""
    script = _step("publish-mcp", "Version bestimmen")["run"]
    work = tmp_path / "repo"
    (work / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "release_version.py", work / "scripts")
    shutil.copy(ROOT / "pyproject.toml", work)
    out = tmp_path / "github_output"
    out.write_text("")
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=work,
        env={"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(out), **env},
        capture_output=True,
        text=True,
    )
    return proc.returncode, out.read_text(), proc.stdout + proc.stderr


@pytest.fixture
def repo_version() -> str:
    return pyproject_version(ROOT / "pyproject.toml")


def test_step_release_with_capital_v(tmp_path, repo_version):
    code, output, _ = _run_version_step(
        tmp_path, GITHUB_EVENT_NAME="release", GITHUB_REF_NAME=f"V{repo_version}"
    )
    assert code == 0
    assert output.strip() == f"version={repo_version}"


def test_step_release_with_wrong_tag_fails(tmp_path):
    code, output, log = _run_version_step(
        tmp_path, GITHUB_EVENT_NAME="release", GITHUB_REF_NAME="v99.0.0"
    )
    assert code != 0
    assert output == ""
    assert "passt nicht zu pyproject.toml" in log


def test_step_manual_on_main(tmp_path, repo_version):
    code, output, _ = _run_version_step(
        tmp_path, GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/main"
    )
    assert code == 0
    assert output.strip() == f"version={repo_version}"


def test_step_manual_on_other_branch_fails(tmp_path):
    code, output, log = _run_version_step(
        tmp_path, GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/feature"
    )
    assert code != 0
    assert output == ""
    assert "nur von main" in log
