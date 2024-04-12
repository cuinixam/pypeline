import json
from pathlib import Path
from unittest.mock import Mock, patch

from py_app_dev.core.scoop_wrapper import InstalledScoopApp, ScoopWrapper

from pypeline.steps.scoop_install import ScoopInstall


def test_scoop_install_with_mocked_wrapper(execution_context: Mock) -> None:
    # Setup the scoop_file.json and other initial configurations
    scoop_file_json = execution_context.project_root_dir.joinpath("scoopfile.json")
    scoop_file_json.write_text("")

    expected_paths = [Path("some/path"), Path("some/path/bin"), Path("some/path/env")]

    mock_scoop_wrapper = Mock(spec=ScoopWrapper)
    mock_scoop_wrapper.install.return_value = [
        InstalledScoopApp(name="app1", version="1.0.0", path=Path("some/path"), bin_dirs=[Path("bin")], env_add_path=[Path("env")], manifest_file=Path("some/manifest"))
    ]

    # Patch the create_scoop_wrapper to return the mock_scoop_wrapper
    with patch("pypeline.steps.scoop_install.create_scoop_wrapper", return_value=mock_scoop_wrapper):
        scoop_install = ScoopInstall(execution_context, execution_context.project_root_dir)
        scoop_install.run()

    mock_scoop_wrapper.install.assert_called_once_with(scoop_file_json)
    execution_info_file = execution_context.project_root_dir.joinpath("scoop_install_exec_info.json")
    assert execution_info_file.exists(), "Execution info file shall exist"
    assert json.loads(execution_info_file.read_text()) == {"install_dirs": [str(path) for path in expected_paths]}

    # Update the execution context with the install directories and verify the call
    scoop_install.update_execution_context()
    execution_context.add_install_dirs.assert_called_once_with(expected_paths)
