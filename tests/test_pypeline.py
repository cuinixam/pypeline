import textwrap
from pathlib import Path
from typing import List, Type, cast
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.config import ProjectConfig
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineConfig, PipelineStep, PipelineStepReference
from pypeline.pypeline import PipelineLoader, PipelineScheduler, PipelineStepsExecutor
from pypeline.steps.create_venv import CreateVEnv
from tests.utils import assert_element_of_type


@pytest.fixture
def pipeline_config(project: Path) -> PipelineConfig:
    return ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline


def test_pipeline_loader(project: Path, pipeline_config: PipelineConfig) -> None:
    steps_references = PipelineLoader[ExecutionContext](pipeline_config, project).load_steps_references()
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
    steps_references = PipelineLoader[ExecutionContext](
        ProjectConfig.from_file(config_file).pipeline,
        tmp_path,
    ).load_steps_references()
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"


def test_pipeline_create_run_command_step_class(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor(
        execution_context,
        [
            PipelineStepReference("my_cmd", cast(Type[PipelineStep[ExecutionContext]], PipelineLoader._create_run_command_step_class("echo 'Hello'", "Echo"))),
        ],
    )
    executor.run()
    assert not len(list(execution_context.project_root_dir.glob("build/my_cmd/*.deps.json"))), "Step dependencies file shall not exist"


def test_pipeline_scheduler(project: Path, pipeline_config: PipelineConfig) -> None:
    scheduler = PipelineScheduler[ExecutionContext](pipeline_config, project)
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


class MyCustomPipelineStep(PipelineStep[ExecutionContext]):
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


def test_pipeline_executor(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor(execution_context, [PipelineStepReference("MyStep", cast(Type[PipelineStep[ExecutionContext]], MyCustomPipelineStep))])
    executor.run()
    assert execution_context.project_root_dir.joinpath("build/MyStep/MyCustomPipelineStep.deps.json").exists(), "Step dependencies file shall exist"


def test_pipeline_executor_dry_run(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor(
        execution_context,
        [
            PipelineStepReference("venv", cast(Type[PipelineStep[ExecutionContext]], CreateVEnv), {"bootstrap_script": "does_not_exist.py"}),
        ],
        dry_run=True,
    )
    executor.run()
    assert not execution_context.project_root_dir.joinpath("build/venv/CreateVEnvStep.deps.json").exists(), "Step dependencies file shall not exist"
    # If the step is actually executed it fails because the bootstrap script does not exist
    executor.dry_run = False
    with pytest.raises(UserNotificationException):
        executor.run()


class MyExecutionContext(ExecutionContext):
    def __init__(self, project_root_dir: Path, extra_info: str) -> None:
        super().__init__(project_root_dir)
        self.extra_info = extra_info


class MyCustomPipelineStepWithContext(PipelineStep[MyExecutionContext]):
    def run(self) -> int:
        return 0

    def get_name(self) -> str:
        return "MyCustomPipelineStepWithContext"

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        self.execution_context.extra_info = "updated"


def test_pipeline_executor_with_custom_context(project: Path) -> None:
    execution_context = MyExecutionContext(project, "initial")
    executor = PipelineStepsExecutor(
        execution_context,
        [PipelineStepReference("MyStep", cast(Type[PipelineStep[MyExecutionContext]], MyCustomPipelineStepWithContext))],
    )
    executor.run()
    assert execution_context.extra_info == "updated"
