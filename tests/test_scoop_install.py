import json
import unittest.mock
from pathlib import Path
from typing import List

from py_app_dev.core.scoop_wrapper import InstalledScoopApp

from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.scoop_install import ScoopInstall


def test_scoop_install(execution_context: ExecutionContext) -> None:
    scoop_file_json = execution_context.project_root_dir.joinpath("scoopfile.json")
    scoop_file_json.write_text("")
    scoop_install = ScoopInstall(execution_context, execution_context.project_root_dir)
    installed_apps: List[InstalledScoopApp] = [
        InstalledScoopApp(name="app1", version="1.0.0", path=Path("some/path"), bin_dirs=[Path("bin")], env_add_path=[Path("env")], manifest_file=Path("some/manifest"))
    ]
    expected_paths = [Path("some/path"), Path("some/path/bin"), Path("some/path/env")]

    # run the step
    with unittest.mock.patch("py_app_dev.core.scoop_wrapper.ScoopWrapper.install", return_value=installed_apps) as scoop_wrapper_install:
        scoop_install.run()

    scoop_wrapper_install.assert_called_once_with(scoop_file_json)
    execution_info_file = execution_context.project_root_dir.joinpath("scoop_install_exec_info.json")
    assert execution_info_file.exists(), "Execution info file shall exist"
    assert json.loads(execution_info_file.read_text()) == {"install_dirs": [str(path) for path in expected_paths]}

    # update the execution context with the install directories
    scoop_install.update_execution_context()
    execution_context.add_install_dirs.assert_called_once_with(expected_paths)
