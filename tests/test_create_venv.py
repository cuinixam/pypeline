from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.steps.create_venv import CreateVEnv, CreateVEnvDeps


@pytest.mark.parametrize("bootstrap_script", [".bootstrap/bootstrap.py", "custom_bootstrap.py"])
def test_create_venv_with_custom_script(execution_context: Mock, bootstrap_script: Optional[str]) -> None:
    bootstrap_py = execution_context.project_root_dir.joinpath(bootstrap_script)
    bootstrap_py.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_py.write_text("")
    config = {"bootstrap_script": bootstrap_script} if bootstrap_script else None
    create_venv = CreateVEnv(execution_context, "group_name", config)
    create_venv.run()
    # check that the bootstrap.py script is executed
    execution_context.create_process_executor.assert_called_once_with(["python311", bootstrap_py.as_posix()], cwd=execution_context.project_root_dir)


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
            "python311",
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
    deps_file.write_text('{"outputs": {"C:/some/path/Scripts": "", "C:/another/path/bin": ""}}')

    install_dirs = create_venv.install_dirs

    assert len(install_dirs) == 2
    assert Path("C:/some/path/Scripts") in install_dirs
    assert Path("C:/another/path/bin") in install_dirs


def test_install_dirs_fallback_without_deps_file(execution_context: Mock) -> None:
    create_venv = CreateVEnv(execution_context, "group_name")

    venv_scripts = execution_context.project_root_dir / ".venv" / "Scripts"
    venv_scripts.mkdir(parents=True, exist_ok=True)

    install_dirs = create_venv.install_dirs

    assert len(install_dirs) == 1
    assert execution_context.project_root_dir / ".venv" / "Scripts" in install_dirs


def test_create_venv_deps_from_json_file_with_dict_outputs(tmp_path: Path) -> None:
    deps_file = tmp_path / "test-deps.json"
    deps_file.write_text('{ "outputs": { "/path/to/Scripts": "", "/path/to/bin": "" } }')

    deps = CreateVEnvDeps.from_json_file(deps_file)

    assert deps.outputs == [Path("/path/to/Scripts"), Path("/path/to/bin")]


def test_create_venv_deps_from_json_file_with_list_outputs(tmp_path: Path) -> None:
    deps_file = tmp_path / "test-deps.json"
    deps_file.write_text('{"outputs": ["/path/to/Scripts", "/path/to/bin"]}')

    deps = CreateVEnvDeps.from_json_file(deps_file)

    assert deps.outputs == [Path("/path/to/Scripts"), Path("/path/to/bin")]
