import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.execution_context import ExecutionContext


@pytest.fixture
def project(tmp_path: Path) -> Path:
    custom_step_py = tmp_path / "my_python_file.py"
    custom_step_py.write_text(
        textwrap.dedent(
            """\
            from typing import List
            from pathlib import Path
            from pypeline.domain.execution_context import ExecutionContext
            from pypeline.domain.pipeline import PipelineStep
            class MyData:
                def __init__(self, data: str) -> None:
                    self.data = data
            class BaseStep(PipelineStep[ExecutionContext]):
                def run(self) -> None:
                    pass
                def get_inputs(self) -> List[Path]:
                    return []
                def get_outputs(self) -> List[Path]:
                    return []
                def get_name(self) -> str:
                    return self.__class__.__name__
                def update_execution_context(self) -> None:
                    pass
            class MyStep(BaseStep):
                def run(self) -> None:
                    self.execution_context.data_registry.insert(MyData("some data"), self.get_name())
            class MyStepChecker(BaseStep):
                def run(self) -> None:
                    data = self.execution_context.data_registry.find_data(MyData)
                    if not data:
                        raise ValueError("Data not found")
            class MyInputsChecker(BaseStep):
                def run(self) -> None:
                    input = self.execution_context.inputs.get("my_input")
                    if not input:
                        raise ValueError("Input not found")
                    if input != "my_value":
                        raise ValueError("Input value is not 'value'")
            """
        )
    )
    pypeline_config = tmp_path / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                custom:
                    - step: MyStep
                      file: my_python_file.py
                      config:
                            input: value
                install:
                    - step: ScoopInstall
                      module: pypeline.steps.scoop_install
                    - step: Echo
                      run: echo 'Hello'
                      description: Simple step that runs a command
                commands:
                    - step: CheckPython
                      run: python --version
            """
        )
    )
    # Create a custom pypeline definition file for testing the `--config-file` option
    tmp_path.joinpath("my_pypeline.yaml").write_text(pypeline_config.read_text())
    return tmp_path


@pytest.fixture
def artifacts_locator(project: Path) -> ProjectArtifactsLocator:
    return ProjectArtifactsLocator(project)


@pytest.fixture
def execution_context(project: Path) -> Mock:
    execution_context = Mock(spec=ExecutionContext)
    execution_context.project_root_dir = project
    execution_context.create_artifacts_locator.return_value = ProjectArtifactsLocator(project)
    # Configure get_input to return None by default (tests can override this)
    execution_context.get_input.return_value = None
    return execution_context
