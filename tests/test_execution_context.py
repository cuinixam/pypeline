from pathlib import Path

from pypeline.domain.execution_context import ExecutionContext


def test_execution_context(project: Path) -> None:
    execution_context = ExecutionContext(project_root_dir=project)
    assert execution_context.project_root_dir == project
    # add some install directories
    execution_context.add_install_dirs([Path("dir1"), Path("dir2")])
    # creating a process executor shall add the install directories to the environment
    subprocess_executor = execution_context.create_process_executor(["some_command"])
    assert subprocess_executor.env
    assert all(directory in subprocess_executor.env["PATH"] for directory in ["dir1", "dir2"])


def test_create_process_executor_with_env_vars(project: Path) -> None:
    context = ExecutionContext(project_root_dir=project)
    env_vars = {"TEST_VAR": "value"}
    context.add_env_vars(env_vars)

    # Add some install directories
    context.add_install_dirs([Path("dir1"), Path("dir2")])

    # Create process executor
    subprocess_executor = context.create_process_executor(["some_command"])

    assert subprocess_executor.env
    assert subprocess_executor.env["TEST_VAR"] == "value"
    assert all(directory in subprocess_executor.env["PATH"] for directory in ["dir1", "dir2"])
    assert "value" in subprocess_executor.env.values()


class SomeData:
    def __init__(self, data: str) -> None:
        self.data = data


def test_execution_context_exchange_data(project: Path) -> None:
    execution_context = ExecutionContext(project_root_dir=project)
    # exchange data
    execution_context.data_registry.insert(SomeData("my data"), "abc")
    execution_context.data_registry.insert(SomeData("new data"), "abc")
    my_data = execution_context.data_registry.find_data(SomeData)
    assert [entry.data for entry in my_data] == ["my data", "new data"]


def test_add_env_vars():
    context = ExecutionContext(project_root_dir=Path("/dummy/path"))
    env_vars = {"TEST_VAR": "value", "ANOTHER_VAR": 123}

    # Add environment variables
    context.add_env_vars(env_vars)

    # Assert that the environment variables were added correctly
    assert context.env_vars["TEST_VAR"] == "value"
    assert context.env_vars["ANOTHER_VAR"] == 123
