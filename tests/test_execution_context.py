from pathlib import Path

from pypeline.domain.execution_context import ExecutionContext


def test_execution_context(project: Path) -> None:
    execution_context = ExecutionContext(project)
    assert execution_context.project_root_dir == project
    # add some install directories
    execution_context.add_install_dirs([Path("dir1"), Path("dir2")])
    # creating a process executor shall add the install directories to the environment
    subprocess_executor = execution_context.create_process_executor(["some_command"])
    assert subprocess_executor.env
    assert all(directory in subprocess_executor.env["PATH"] for directory in ["dir1", "dir2"])


class SomeData:
    def __init__(self, data: str) -> None:
        self.data = data


def test_execution_context_exchange_data(project: Path) -> None:
    execution_context = ExecutionContext(project)
    # exchange data
    execution_context.data_registry.insert(SomeData("my data"), "abc")
    execution_context.data_registry.insert(SomeData("new data"), "abc")
    my_data = execution_context.data_registry.find_data(SomeData)
    assert [entry.data for entry in my_data] == ["my data", "new data"]
