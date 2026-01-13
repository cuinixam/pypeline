import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.steps.create_venv import CreateVEnv, CreateVEnvDeps


@pytest.mark.parametrize("bootstrap_script", [".bootstrap/bootstrap.py", "custom_bootstrap.py"])
def test_create_venv_with_custom_script(execution_context: Mock, bootstrap_script: str) -> None:
    # Create the bootstrap script file
    bootstrap_path = execution_context.project_root_dir / bootstrap_script
    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_path.write_text("")

    # Pass bootstrap script via config
    config = {"bootstrap_script": bootstrap_script}
    create_venv = CreateVEnv(execution_context, "group_name", config)
    create_venv.run()
    # check that the custom bootstrap script is executed
    execution_context.create_process_executor.assert_called_once_with(
        [sys.executable, bootstrap_path.as_posix()],
        cwd=execution_context.project_root_dir,
    )


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
            sys.executable,
            Path(execution_context.project_root_dir).joinpath(".bootstrap/bootstrap.py").as_posix(),
            "--project-dir",
            Path(execution_context.project_root_dir).as_posix(),
        ],
        cwd=execution_context.project_root_dir,
    )


def test_install_dirs_from_deps_file(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name")
    deps_file = execution_context.project_root_dir / ".venv" / "create-virtual-environment.deps.json"
    deps_file.parent.mkdir(parents=True, exist_ok=True)
    deps_file.write_text('{"outputs": ["/path/to/Scripts", "/path/to/bin"]}')
    install_dirs = create_venv.install_dirs
    assert install_dirs == [Path("/path/to/Scripts"), Path("/path/to/bin")]


def test_install_dirs_fallback_without_deps_file(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name")
    project = execution_context.project_root_dir
    scripts_dir = project / ".venv/Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    install_dirs = create_venv.install_dirs
    assert install_dirs == [project / ".venv/Scripts"]


def test_create_venv_deps_from_json_file_with_dict_outputs(tmp_path: Path) -> None:
    deps_file = tmp_path / "test-deps.json"
    deps_file.write_text('{"outputs": {"/path/to/Scripts": null, "/path/to/bin": null}}')

    deps = CreateVEnvDeps.from_json_file(deps_file)

    assert deps.outputs == [Path("/path/to/Scripts"), Path("/path/to/bin")]


def test_create_venv_deps_from_json_file_with_list_outputs(tmp_path: Path) -> None:
    deps_file = tmp_path / "test-deps.json"
    deps_file.write_text('{"outputs": ["/path/to/Scripts", "/path/to/bin"]}')

    deps = CreateVEnvDeps.from_json_file(deps_file)

    assert deps.outputs == [Path("/path/to/Scripts"), Path("/path/to/bin")]


@pytest.mark.parametrize(
    "python_version, available_executable, expected_result",
    [
        # Version with minor: should find python3.11 or python311
        ("3.11", "python3.11", "python3.11"),
        ("3.11", "python311", "python311"),
        ("3.11.5", "python3.11", "python3.11"),  # Ignores patch version
        # Version with major only: should find python3
        ("3", "python3", "python3"),
        # Not found: should return None (no fallback)
        ("3.12", None, None),
        # Empty: should return None
        ("", None, None),
    ],
)
def test_find_python_executable(execution_context: Mock, python_version: str, available_executable: str | None, expected_result: str | None) -> None:
    config = {"python_version": python_version} if python_version else {}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    def mock_which(candidate: str) -> str | None:
        # Only return a path if this is the available executable
        if candidate == available_executable:
            return f"/usr/bin/{candidate}"
        return None

    with patch("shutil.which", side_effect=mock_which):
        result = create_venv._find_python_executable(python_version)

    assert result == expected_result


@pytest.mark.parametrize(
    "config, available_executables, expected_result",
    [
        # Explicit python_executable - should use it directly
        ({"python_executable": "python3.11"}, [], "python3.11"),
        # python_version with available executable - should find it
        ({"python_version": "3.11"}, ["python3.11"], "python3.11"),
        # No config - should fall back to sys.executable
        ({}, [], sys.executable),
    ],
)
def test_python_executable_property(execution_context: Mock, config: dict[str, str], available_executables: list[str], expected_result: str) -> None:
    create_venv = CreateVEnv(execution_context, "group_name", config)

    def mock_which(candidate: str) -> str | None:
        if candidate in available_executables:
            return f"/usr/bin/{candidate}"
        return None

    with patch("shutil.which", side_effect=mock_which):
        result = create_venv.python_executable

    assert result == expected_result


def test_python_executable_property_version_not_found(execution_context: Mock) -> None:
    config = {"python_version": "3.99"}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    with patch("shutil.which", return_value=None):
        with pytest.raises(UserNotificationException, match=r"Could not find Python 3\.99"):
            _ = create_venv.python_executable


def test_bootstrap_config_file_in_bootstrap_directory(execution_context: Mock) -> None:
    config = {"package_manager": "uv>=0.6"}
    create_venv = CreateVEnv(execution_context, "group_name", config)
    create_venv.run()

    # Check that bootstrap.json is in .bootstrap directory
    bootstrap_config_file = execution_context.project_root_dir / ".bootstrap" / "bootstrap.json"
    assert bootstrap_config_file.exists()

    # Ensure it's not in the project root
    root_bootstrap_file = execution_context.project_root_dir / "bootstrap.json"
    assert not root_bootstrap_file.exists()
