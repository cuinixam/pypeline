from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import pytest

from pypeline.steps.create_venv import CreateVEnv


@pytest.mark.parametrize("bootstrap_script", [None, ".bootstrap/bootstrap.py", "custom_bootstrap.py"])
def test_create_venv(execution_context: Mock, bootstrap_script: Optional[str]) -> None:
    bootstrap_py = execution_context.project_root_dir.joinpath(bootstrap_script or "bootstrap.py")
    bootstrap_py.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_py.write_text("")
    config = {"bootstrap_script": bootstrap_script} if bootstrap_script else None
    create_venv = CreateVEnv(execution_context, Path("out"), config)
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(["python", bootstrap_py.as_posix()], cwd=execution_context.project_root_dir)
    # check that the install directories are added to the execution context
    execution_context.add_install_dirs.assert_called_once()
