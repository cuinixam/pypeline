from pathlib import Path

from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.create_venv import CreateVEnv


def test_create_venv(execution_context: ExecutionContext) -> None:
    bootstrap_py = execution_context.project_root_dir.joinpath("bootstrap.py")
    bootstrap_py.write_text("")
    create_venv = CreateVEnv(execution_context, Path("out"))
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(["python", bootstrap_py.as_posix()], cwd=execution_context.project_root_dir)
    # check that the install directories are added to the execution context
    execution_context.add_install_dirs.assert_called_once()
