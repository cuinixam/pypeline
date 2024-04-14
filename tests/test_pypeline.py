from pathlib import Path
from typing import List, Type, cast

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.pipeline import PipelineConfig

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.config import ProjectConfig
from pypeline.domain.pipeline import PipelineStep, PipelineStepReference
from pypeline.pypeline import PipelineLoader, PipelineScheduler, PipelineStepsExecutor
from pypeline.steps.create_venv import CreateVEnv


@pytest.fixture
def pipeline_config(project: Path) -> PipelineConfig:
    return ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline


def test_pipeline_loader(project: Path, pipeline_config: PipelineConfig) -> None:
    steps_references = PipelineLoader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_scheduler(project: Path, pipeline_config: PipelineConfig) -> None:
    scheduler = PipelineScheduler(pipeline_config, project)
    # All steps shall be scheduled
    steps_references = scheduler.get_steps_to_run()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall"]
    # Only the step with the provided name shall be scheduled
    steps_references = scheduler.get_steps_to_run(step_name="MyStep")
    assert [step_ref.name for step_ref in steps_references] == ["MyStep"]
    # Single step execution
    steps_references = scheduler.get_steps_to_run(step_name="ScoopInstall", single=True)
    assert [step_ref.name for step_ref in steps_references] == ["ScoopInstall"]
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
