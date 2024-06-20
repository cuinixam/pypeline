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
            from pypeline.domain.pipeline import PipelineStep
            class MyStep(PipelineStep):
                def run(self) -> None:
                    pass
                def get_inputs(self) -> List[Path]:
                    return []
                def get_outputs(self) -> List[Path]:
                    return []
                def get_name(self) -> str:
                    return "MyStep"
                def update_execution_context(self) -> None:
                    pass
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
            """
        )
    )
    return tmp_path


@pytest.fixture
def artifacts_locator(project: Path) -> ProjectArtifactsLocator:
    return ProjectArtifactsLocator(project)


@pytest.fixture
def execution_context(project: Path) -> Mock:
    execution_context = Mock(spec=ExecutionContext)
    execution_context.project_root_dir = project
    execution_context.create_artifacts_locator.return_value = ProjectArtifactsLocator(project)
    return execution_context
