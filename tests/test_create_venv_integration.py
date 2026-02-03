import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.create_venv import CreateVEnv


@pytest.mark.parametrize(
    "bootstrap_script",
    [
        ".bootstrap\\bootstrap.py",
        r".bootstrap\bootstrap.py",
        ".bootstrap/bootstrap.py",
    ],
)
def test_create_venv_bootstrap_path_normalization(tmp_path: Path, bootstrap_script: str) -> None:
    mock_context = MagicMock(spec=ExecutionContext)
    mock_context.project_root_dir = tmp_path
    mock_context.create_process_executor.return_value.execute.return_value = 0
    mock_context.get_input.return_value = None

    config = {"bootstrap_script": bootstrap_script}
    step = CreateVEnv(mock_context, "integration_test_group", config)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(step, "_find_python_executable", lambda v: sys.executable)
        step.run()

    bootstrap_file = tmp_path / ".bootstrap" / "bootstrap.py"
    assert bootstrap_file.exists()
    assert bootstrap_file.is_file()

    # Ensure no file with backslash in name exists on POSIX
    weird_file = tmp_path / r".bootstrap\bootstrap.py"
    if weird_file.name != "bootstrap.py":
        assert not weird_file.exists()


def test_create_venv_internal_script_defaults(tmp_path: Path) -> None:
    mock_context = MagicMock(spec=ExecutionContext)
    mock_context.project_root_dir = tmp_path
    mock_context.create_process_executor.return_value.execute.return_value = 0
    mock_context.get_input.return_value = None

    step = CreateVEnv(mock_context, "integration_test_group")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(step, "_find_python_executable", lambda v: sys.executable)
        step.run()

    bootstrap_file = tmp_path / ".bootstrap" / "bootstrap.py"
    assert bootstrap_file.exists()
