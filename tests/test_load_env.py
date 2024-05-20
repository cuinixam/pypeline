from pathlib import Path
from unittest.mock import Mock

from pypeline.steps.load_env import LoadEnv


def test_load_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=value1\nKEY2=value2\n# This is a comment\nKEY3=value3\n")

    expected_env_vars = {
        "KEY1": "value1",
        "KEY2": "value2",
        "KEY3": "value3",
    }

    env_vars = LoadEnv.load_dot_env_file(env_file)

    assert env_vars == expected_env_vars


def test_update_execution_context_with_env_file(execution_context: Mock, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=value1\nKEY2=value2")

    load_env_step = LoadEnv(execution_context=execution_context, output_dir=tmp_path)

    load_env_step.update_execution_context()

    execution_context.add_env_vars.assert_called_once_with({"KEY1": "value1", "KEY2": "value2"})


def test_update_execution_context_without_env_file(execution_context: Mock, tmp_path: Path) -> None:
    load_env_step = LoadEnv(execution_context=execution_context, output_dir=tmp_path)

    load_env_step.update_execution_context()

    execution_context.add_env_vars.assert_not_called()


def test_get_needs_dependency_management(execution_context: Mock, tmp_path: Path) -> None:
    load_env_step = LoadEnv(execution_context=execution_context, output_dir=tmp_path)

    assert load_env_step.get_needs_dependency_management() is False
