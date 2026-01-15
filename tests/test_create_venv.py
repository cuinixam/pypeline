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


@pytest.mark.parametrize(
    "input_python_version, available_executables, expected_result",
    [
        # Input python_version takes highest priority
        ("3.10", ["python3.10"], "python3.10"),
        ("3.13", ["python313"], "python313"),
        ("3.11.5", ["python3.11"], "python3.11"),  # Ignores patch version
    ],
)
def test_python_executable_from_execution_context_input(execution_context: Mock, input_python_version: str, available_executables: list[str], expected_result: str) -> None:
    # Set python_version in execution context inputs
    execution_context.get_input.return_value = input_python_version

    # No config specified - input should take priority over sys.executable
    create_venv = CreateVEnv(execution_context, "group_name", {})

    def mock_which(candidate: str) -> str | None:
        if candidate in available_executables:
            return f"/usr/bin/{candidate}"
        return None

    with patch("shutil.which", side_effect=mock_which):
        result = create_venv.python_executable

    assert result == expected_result


def test_python_executable_from_execution_context_input_not_found(execution_context: Mock) -> None:
    # Set python_version in execution context inputs
    execution_context.get_input.return_value = "3.99"

    create_venv = CreateVEnv(execution_context, "group_name", {})

    with patch("shutil.which", return_value=None):
        with pytest.raises(UserNotificationException, match=r"Could not find Python 3\.99"):
            _ = create_venv.python_executable


def test_python_executable_input_overrides_config(execution_context: Mock) -> None:
    # Input should override config python_version
    execution_context.get_input.return_value = "3.13"

    # Config specifies different version
    config = {"python_version": "3.10"}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    def mock_which(candidate: str) -> str | None:
        if candidate == "python313":
            return "/usr/bin/python313"
        return None

    with patch("shutil.which", side_effect=mock_which):
        result = create_venv.python_executable

    # Should use input version (3.13) not config version (3.10)
    assert result == "python313"


def test_python_version_input_written_to_bootstrap_config(execution_context: Mock) -> None:
    # Set python_version in execution context inputs
    execution_context.get_input.return_value = "3.13"

    config = {"package_manager": "uv>=0.6"}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    def mock_which(candidate: str) -> str | None:
        if candidate == "python313":
            return "/usr/bin/python313"
        return None

    with patch("shutil.which", side_effect=mock_which):
        create_venv.run()

    # Check that bootstrap.json contains the input python_version
    bootstrap_config_file = execution_context.project_root_dir / ".bootstrap" / "bootstrap.json"
    assert bootstrap_config_file.exists()

    import json

    bootstrap_config = json.loads(bootstrap_config_file.read_text())
    assert bootstrap_config["python_version"] == "3.13"


@pytest.mark.parametrize(
    "executable, expected_version, version_output, expected_result",
    [
        # Matching versions
        ("python", "3.11", "Python 3.11.5", True),
        ("python", "3.10", "Python 3.10.0", True),
        ("python3", "3.12", "Python 3.12.1", True),
        # Mismatched versions
        ("python", "3.11", "Python 3.10.5", False),
        ("python", "3.13", "Python 3.12.0", False),
        # Different version formats
        ("python", "3.11", "Python 3.11.5 (default, Aug  7 2024, 17:19:32)", True),
        ("python", "3.10", "Python 3.10.12\n", True),
        # Major version only
        ("python3", "3", "Python 3.11.5", True),
        ("python3", "3", "Python 3.10.0", True),
    ],
)
def test_verify_python_version(execution_context: Mock, executable: str, expected_version: str, version_output: str, expected_result: bool) -> None:
    create_venv = CreateVEnv(execution_context, "group_name", {})

    mock_result = Mock()
    mock_result.stdout = version_output
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        result = create_venv._verify_python_version(executable, expected_version)

    assert result == expected_result


def test_verify_python_version_invalid_executable(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name", {})

    # Simulate subprocess.run raising an exception
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        result = create_venv._verify_python_version("nonexistent_python", "3.11")

    assert result is False


def test_verify_python_version_invalid_output(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name", {})

    mock_result = Mock()
    mock_result.stdout = "invalid output"
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        result = create_venv._verify_python_version("python", "3.11")

    assert result is False


@pytest.mark.parametrize(
    "python_version, available_executable, python_version_output, expected_result",
    [
        # Fallback to python when version-specific not found, version matches
        ("3.11", "python", "Python 3.11.5", "python"),
        ("3.10", "python", "Python 3.10.0", "python"),
        # Fallback to python when version-specific not found, version doesn't match
        ("3.11", "python", "Python 3.10.5", None),
        ("3.13", "python", "Python 3.12.0", None),
        # Version-specific executable found, should not fallback
        ("3.11", "python3.11", "Python 3.11.5", "python3.11"),
        ("3.10", "python310", "Python 3.10.0", "python310"),
    ],
)
def test_find_python_executable_with_fallback(
    execution_context: Mock,
    python_version: str,
    available_executable: str,
    python_version_output: str,
    expected_result: str | None,
) -> None:
    config = {"python_version": python_version}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    def mock_which(candidate: str) -> str | None:
        # Return path for the available executable
        if candidate == available_executable:
            return f"/usr/bin/{candidate}"
        return None

    mock_result = Mock()
    mock_result.stdout = python_version_output
    mock_result.returncode = 0

    with patch("shutil.which", side_effect=mock_which):
        with patch("subprocess.run", return_value=mock_result):
            result = create_venv._find_python_executable(python_version)

    assert result == expected_result


def test_find_python_executable_fallback_no_python_available(execution_context: Mock) -> None:
    config = {"python_version": "3.11"}
    create_venv = CreateVEnv(execution_context, "group_name", config)

    # No executables available
    with patch("shutil.which", return_value=None):
        result = create_venv._find_python_executable("3.11")

    assert result is None
