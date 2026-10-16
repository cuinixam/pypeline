import textwrap
from pathlib import Path
from typing import List

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.config import ProjectConfig
from pypeline.domain.execution_context import ExecutionContext, InstallDir
from pypeline.domain.pipeline import PipelineConfigIterator, PipelineStep


def test_pipeline_iterator_without_groups(tmp_path: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = tmp_path / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                - step: MyStep
                  file: my_python_file.py
                  config:
                    input: value
                - step: ScoopInstall
                  module: pypeline.steps.scoop_install
                - step: Echo
                  run: echo 'Hello'
                  description: Simple step that runs a command
            """
        )
    )
    pipeline_config = ProjectConfig.from_file(pypeline_config).pipeline
    # Consume the iterator
    assert [None] == [item[0] for item in PipelineConfigIterator(pipeline_config)]


def test_pipeline_iterator_with_groups(tmp_path: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = tmp_path / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                group1:
                  - step: ScoopInstall
                    module: pypeline.steps.scoop_install
                group2:
                  - step: Echo
                    run: echo 'Hello'
                    description: Simple step that runs a command
            """
        )
    )
    pipeline_config = ProjectConfig.from_file(pypeline_config).pipeline
    # Consume the iterator
    assert ["group1", "group2"] == [item[0] for item in PipelineConfigIterator(pipeline_config)]


class InstallingStep(PipelineStep[ExecutionContext]):
    def run(self) -> int:
        return 0

    def get_name(self) -> str:
        return "InstallingStep"

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        self.add_install_dirs([Path("tool")])


def test_step_config_install_dirs_order_overrides_the_step_order(tmp_path: Path) -> None:
    context = ExecutionContext(project_root_dir=tmp_path)
    context.add_install_dirs([InstallDir(Path("venv"), order=0)])
    InstallingStep(context, None, {"install_dirs_order": -1}).update_execution_context()

    assert context.install_dirs == (Path("tool"), Path("venv"))


def test_step_without_install_dirs_order_uses_the_default_order(tmp_path: Path) -> None:
    context = ExecutionContext(project_root_dir=tmp_path)
    InstallingStep(context, None).update_execution_context()
    context.add_install_dirs([InstallDir(Path("venv"), order=0)])

    assert context.install_dirs == (Path("venv"), Path("tool"))


def test_step_config_install_dirs_order_must_be_an_integer(tmp_path: Path) -> None:
    step = InstallingStep(ExecutionContext(project_root_dir=tmp_path), None, {"install_dirs_order": "10"})

    with pytest.raises(UserNotificationException, match="install_dirs_order"):
        step.update_execution_context()
