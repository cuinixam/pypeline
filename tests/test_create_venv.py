from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import pytest

from pypeline.bootstrap.run import get_bootstrap_script
from pypeline.steps.create_venv import CreateVEnv


@pytest.mark.parametrize("bootstrap_script", [".bootstrap/bootstrap.py", "custom_bootstrap.py"])
def test_create_venv_with_custom_script(execution_context: Mock, bootstrap_script: Optional[str]) -> None:
    bootstrap_py = execution_context.project_root_dir.joinpath(bootstrap_script)
    bootstrap_py.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_py.write_text("")
    config = {"bootstrap_script": bootstrap_script} if bootstrap_script else None
    create_venv = CreateVEnv(execution_context, "group_name", config)
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(["python3", bootstrap_py.as_posix()], cwd=execution_context.project_root_dir)
    # check that the install directories are added to the execution context
    execution_context.add_install_dirs.assert_called_once()


def test_create_venv_with_internal_script(execution_context: Mock) -> None:
    bootstrap_py = get_bootstrap_script()
    create_venv = CreateVEnv(execution_context, "group_name")
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(
        [
            "python3",
            bootstrap_py.as_posix(),
            "--project-dir",
            Path(execution_context.project_root_dir).as_posix(),
        ],
        cwd=execution_context.project_root_dir,
    )
    # check that the install directories are added to the execution context
    execution_context.add_install_dirs.assert_called_once()
