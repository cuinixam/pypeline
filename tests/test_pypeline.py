import textwrap
from pathlib import Path
from typing import List, Type, cast
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.config import ProjectConfig
from pypeline.domain.pipeline import PipelineConfig, PipelineStep, PipelineStepReference
from pypeline.pypeline import PipelineLoader, PipelineScheduler, PipelineStepsExecutor
from pypeline.steps.create_venv import CreateVEnv
from tests.utils import assert_element_of_type


@pytest.fixture
def pipeline_config(project: Path) -> PipelineConfig:
    return ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline


def test_pipeline_loader(project: Path, pipeline_config: PipelineConfig) -> None:
    steps_references = PipelineLoader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_loader_run_command_step(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Echo
              run: echo 'Hello'
              description: Simple step that runs a command
    """)
    )
    steps_references = PipelineLoader(
        ProjectConfig.from_file(config_file).pipeline,
        tmp_path,
    ).load_steps_references()
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"


def test_pipeline_create_run_command_step_class(artifacts_locator: ProjectArtifactsLocator) -> None:
    executor = PipelineStepsExecutor(
        artifacts_locator,
        [
            PipelineStepReference("my_cmd", cast(Type[PipelineStep], PipelineLoader._create_run_command_step_class("echo 'Hello'", "Echo"))),
        ],
    )
    executor.run()
    assert not len(list(artifacts_locator.build_dir.glob("my_cmd/*.deps.json"))), "Step dependencies file shall not exist"


def test_pipeline_scheduler(project: Path, pipeline_config: PipelineConfig) -> None:
    scheduler = PipelineScheduler(pipeline_config, project)
    # All steps shall be scheduled
    steps_references = scheduler.get_steps_to_run()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo"]
    # Only the step with the provided name shall be scheduled
    steps_references = scheduler.get_steps_to_run(step_name="MyStep")
    assert [step_ref.name for step_ref in steps_references] == ["MyStep"]
    # Single step execution
    steps_references = scheduler.get_steps_to_run(step_name="ScoopInstall", single=True)
    assert [step_ref.name for step_ref in steps_references] == ["ScoopInstall"]
    # Single execution for step with a command
    steps_references = scheduler.get_steps_to_run(step_name="Echo", single=True)
    assert [step_ref.name for step_ref in steps_references] == ["Echo"]
    # No steps are scheduled
    steps_references = scheduler.get_steps_to_run(step_name="MissingStep", single=True)
    assert [step_ref.name for step_ref in steps_references] == []


class MyCustomPipelineStep(PipelineStep):
    def run(self) -> int:
        return 0

    def get_name(self) -> str:
        return "MyCustomPipelineStep"

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        self.execution_context.add_install_dirs([Path("my_install_dir")])


def test_pipeline_executor(artifacts_locator: ProjectArtifactsLocator) -> None:
    executor = PipelineStepsExecutor(artifacts_locator, [PipelineStepReference("MyStep", cast(Type[PipelineStep], MyCustomPipelineStep))])
    executor.run()
    assert artifacts_locator.build_dir.joinpath("MyStep/MyCustomPipelineStep.deps.json").exists(), "Step dependencies file shall exist"


def test_pipeline_executor_dry_run(artifacts_locator: ProjectArtifactsLocator) -> None:
    executor = PipelineStepsExecutor(
        artifacts_locator,
        [
            PipelineStepReference("venv", cast(Type[PipelineStep], CreateVEnv), {"bootstrap_script": "does_not_exist.py"}),
        ],
        dry_run=True,
    )
    executor.run()
    assert not artifacts_locator.build_dir.joinpath("venv/CreateVEnvStep.deps.json").exists(), "Step dependencies file shall not exist"
    # If the step is actually executed it fails because the bootstrap script does not exist
    executor.dry_run = False
    with pytest.raises(UserNotificationException):
        executor.run()
