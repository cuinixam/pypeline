from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

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
    execution_context.create_process_executor.assert_called_once_with(["python311", bootstrap_py.as_posix()], cwd=execution_context.project_root_dir)


def test_create_venv_with_custom_script_not_found(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name", {"bootstrap_script": "custom_bootstrap.py"})
    with pytest.raises(UserNotificationException):
        create_venv.run()


def test_create_venv_with_internal_script(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name")
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(
        [
            "python311",
            Path(execution_context.project_root_dir).joinpath(".bootstrap/bootstrap.py").as_posix(),
            "--project-dir",
            Path(execution_context.project_root_dir).as_posix(),
            "--package-manager",
            '"uv>=0.6"',
        ],
        cwd=execution_context.project_root_dir,
    )
