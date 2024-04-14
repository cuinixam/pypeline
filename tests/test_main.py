from pathlib import Path
from typing import List

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from typer.testing import CliRunner

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.main import app

runner = CliRunner()


def test_run(artifacts_locator: ProjectArtifactsLocator) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--project-dir",
            artifacts_locator.project_root_dir.as_posix(),
            "--step",
            "MyStep",
            "--single",
        ],
    )
    assert result.exit_code == 0
    assert artifacts_locator.build_dir.joinpath("custom/MyStep.deps.json").exists(), "Step dependencies file shall exist"


def test_run_no_pypeline_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", "--project-dir", tmp_path.as_posix()], catch_exceptions=True)
    assert result.exit_code == 1
    assert isinstance(result.exception, UserNotificationException)


@pytest.fixture
def kickstart_files() -> List[str]:
    return [
        ".gitignore",
        "poetry.toml",
        "pypeline.ps1",
        "pypeline.yaml",
        "pyproject.toml",
        "scoopfile.json",
        "bootstrap.py",
        "bootstrap.ps1",
        "steps/my_step.py",
    ]


def test_init_default(kickstart_files: List[str], tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-dir", tmp_path.as_posix()])
    assert result.exit_code == 0

    for file in kickstart_files:
        assert tmp_path.joinpath(file).exists(), f"{file} shall exist"


def test_init_with_force_in_non_empty_directory(project: Path, kickstart_files: List[str]) -> None:
    result = runner.invoke(app, ["init", "--force", "--project-dir", project.as_posix()])
    assert result.exit_code == 0

    for file in kickstart_files:
        assert project.joinpath(file).exists(), f"{file} shall exist"
