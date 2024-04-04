from pathlib import Path

from pypeline.domain.execution_context import ExecutionContext


def test_execution_context(project: Path) -> None:
    execution_context = ExecutionContext(project)
    assert execution_context.project_root_dir == project
    # add some install directories
    execution_context.add_install_dirs([Path("dir1"), Path("dir2")])
    # creating a process executor shall add teh install directories to the environment
    subprocess_executor = execution_context.create_process_executor(["some_command"])
    assert subprocess_executor.env
    assert all(directory in subprocess_executor.env["PATH"] for directory in ["dir1", "dir2"])
