import json
from pathlib import Path
from unittest.mock import Mock, patch

from py_app_dev.core.scoop_wrapper import InstalledScoopApp, ScoopWrapper

from pypeline.steps.scoop_install import ScoopInstall


def test_scoop_install(execution_context: Mock) -> None:
    # Setup the scoop_file.json and other initial configurations
    scoop_file_json = execution_context.project_root_dir.joinpath("scoopfile.json")
    scoop_file_json.write_text("")

    expected_paths = [Path("some/path/bin"), Path("some/path/env")]
    expected_env_vars = {"TEST_VAR": "value", "ANOTHER_VAR": "123"}

    mock_scoop_wrapper = Mock(spec=ScoopWrapper)
    mock_scoop_wrapper.install.return_value = [
        InstalledScoopApp(
            name="app1",
            version="1.0.0",
            path=Path("some/path"),
            bin_dirs=[Path("bin")],
            env_add_path=[Path("env")],
            env_vars=expected_env_vars,
            manifest_file=Path("some/manifest"),
        )
    ]

    # Patch the create_scoop_wrapper to return the mock_scoop_wrapper
    with patch("pypeline.steps.scoop_install.create_scoop_wrapper", return_value=mock_scoop_wrapper):
        scoop_install = ScoopInstall(execution_context, execution_context.project_root_dir)
        scoop_install.run()

    assert len(scoop_install.get_inputs()) == 2, "Two inputs are expected: scoopfile.json and the package __init__.py"
    mock_scoop_wrapper.install.assert_called_once_with(scoop_file_json)
    execution_info_file = execution_context.project_root_dir.joinpath("scoop_install_exec_info.json")
    assert execution_info_file.exists(), "Execution info file shall exist"

    # Verify that both install_dirs and env_vars are stored in the JSON file
    execution_info = json.loads(execution_info_file.read_text())
    assert execution_info["install_dirs"] == [str(path) for path in expected_paths]
    assert execution_info["env_vars"] == expected_env_vars

    # Update the execution context with the install directories and verify the call
    scoop_install.update_execution_context()
    execution_context.add_install_dirs.assert_called_once_with(expected_paths)

    # Verify that environment variables were added to the execution context
    execution_context.add_env_vars.assert_called_once_with(expected_env_vars)
