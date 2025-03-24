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
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor, RunCommandClassFactory
from pypeline.steps.create_venv import CreateVEnv

from .utils import assert_element_of_type


@pytest.fixture
def pipeline_config(project: Path) -> PipelineConfig:
    return ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline


def test_pipeline_loader(project: Path, pipeline_config: PipelineConfig) -> None:
    steps_references = PipelineScheduler[ExecutionContext].create_pipeline_loader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo", "CheckPython"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_loader_without_groups(project: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = project / "pypeline.yaml"
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
    pipeline_config = ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline
    steps_references = PipelineScheduler[ExecutionContext].create_pipeline_loader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_loader_run_command(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Echo
              run: echo "Hello"
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"
    # Execute the step
    executor = PipelineStepsExecutor[ExecutionContext](ExecutionContext(tmp_path), steps_references)
    executor.run()


def test_pipeline_loader_run_command_with_list(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Echo
              run: [python, -c, "print('Hello World')"]
              description: Simple step that runs a command
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"
    # Execute the step
    executor = PipelineStepsExecutor[ExecutionContext](ExecutionContext(tmp_path), steps_references)
    executor.run()


def test_pipeline_create_run_command_step_class(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor[ExecutionContext](
        execution_context,
        [
            PipelineStepReference("my_cmd", cast(Type[PipelineStep[ExecutionContext]], RunCommandClassFactory._create_run_command_step_class(["echo 'Hello'"], "Echo"))),
        ],
    )
    executor.run()
    assert not len(list(execution_context.project_root_dir.glob("build/my_cmd/*.deps.json"))), "Step dependencies file shall not exist"


@pytest.mark.parametrize(
    "step_names, single, expected_steps",
    [
        ([], False, ["MyStep", "ScoopInstall", "Echo", "CheckPython"]),  # All steps
        (["ScoopInstall"], True, ["ScoopInstall"]),  # Single step
        (["ScoopInstall"], False, ["MyStep", "ScoopInstall"]),  # Steps up to the selected step
        (["MyStep"], False, ["MyStep"]),  # Run the first step only
        (["MyStep", "CheckPython"], True, ["MyStep", "CheckPython"]),  # Multiple selected steps
        (["MyStep", "Echo"], False, ["MyStep", "ScoopInstall", "Echo"]),  # Steps up to "Echo"
        (["Echo"], True, ["Echo"]),  # Single "Echo"
    ],
)
def test_pipeline_scheduler(project: Path, pipeline_config: PipelineConfig, step_names: List[str], single: bool, expected_steps: List[str]) -> None:
    scheduler = PipelineScheduler[ExecutionContext](pipeline_config, project)
    steps_references = scheduler.get_steps_to_run(step_names=step_names, single=single)
    assert [step_ref.name for step_ref in steps_references] == expected_steps


@pytest.mark.parametrize(
    "step_names, single",
    [
        (["MissingStep"], True),
        (["MyStep", "CheckPython", "MissingStep"], True),
        (["MyStep", "CheckPython", "MissingStep"], False),
    ],
)
def test_pipeline_scheduler_exceptions(project: Path, pipeline_config: PipelineConfig, step_names: List[str], single: bool) -> None:
    scheduler = PipelineScheduler[ExecutionContext](pipeline_config, project)
    with pytest.raises(UserNotificationException):
        scheduler.get_steps_to_run(step_names=step_names, single=single)


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


def test_pipeline_exchange_information_between_steps(project: Path) -> None:
    config_file = project / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: MyStep
                  file: my_python_file.py
                - step: MyStepChecker
                  file: my_python_file.py
            """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            project,
        )
        .load_steps_references()
    )
    # Execute pypeline
    execution_context = ExecutionContext(project)
    executor = PipelineStepsExecutor[ExecutionContext](execution_context, steps_references)
    executor.run()
    my_data = [entry for entries in execution_context.data_registry._registry.values() for entry in entries if entry.provider_name == "MyStep"]
    assert len(my_data) == 1, "MyData shall be inserted in the data registry"
