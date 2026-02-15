import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from poks.domain import PoksConfig
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.poks_install import PoksInstall, PoksInstallExecutionInfo


def test_poks_config_data() -> None:
    poks_content = {
        "buckets": [{"name": "tools", "url": "https://github.com/example/bucket"}],
        "apps": [
            {"name": "cmake", "version": "3.28.1", "bucket": "tools"},
            {"name": "ninja", "version": "1.11.1", "bucket": "tools"},
        ],
    }
    config = PoksConfig.from_dict(poks_content)
    assert config.buckets[0].name == "tools"
    assert {app.name for app in config.apps} == {"cmake", "ninja"}
    # Check serialization back to dict
    assert json.loads(config.to_json_string()) == poks_content


def test_poks_config_from_file(tmp_path: Path) -> None:
    poks_content = {
        "buckets": [
            {"name": "main", "url": "https://github.com/example/main"},
            {"name": "extras", "url": "https://github.com/example/extras"},
        ],
        "apps": [
            {"name": "cmake", "version": "3.28.1", "bucket": "main"},
            {"name": "ninja", "version": "1.11.1", "bucket": "extras"},
        ],
    }

    config_file = tmp_path / "poks.json"
    config_file.write_text(json.dumps(poks_content, indent=2))

    config = PoksConfig.from_file(config_file)

    assert len(config.buckets) == 2
    assert next(b for b in config.buckets if b.name == "main").url == "https://github.com/example/main"
    assert next(b for b in config.buckets if b.name == "extras").url == "https://github.com/example/extras"

    assert len(config.apps) == 2
    assert next(a for a in config.apps if a.name == "cmake").version == "3.28.1"
    assert next(a for a in config.apps if a.name == "ninja").version == "1.11.1"


def test_poks_install_execution_info_serialization(tmp_path: Path) -> None:
    execution_info = PoksInstallExecutionInfo(
        install_dirs=[tmp_path / "app1" / "bin", tmp_path / "app2" / "bin"],
        env_vars={"TOOLCHAIN_PATH": "/some/path", "SDK_ROOT": "/sdk"},
    )

    info_file = tmp_path / "execution_info.json"
    execution_info.to_json_file(info_file)
    assert info_file.exists()

    loaded_info = PoksInstallExecutionInfo.from_json_file(info_file)
    assert len(loaded_info.install_dirs) == 2
    assert tmp_path / "app1" / "bin" in loaded_info.install_dirs
    assert tmp_path / "app2" / "bin" in loaded_info.install_dirs
    assert loaded_info.env_vars["TOOLCHAIN_PATH"] == "/some/path"
    assert loaded_info.env_vars["SDK_ROOT"] == "/sdk"


def test_poks_install_with_no_dependencies(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._collect_dependencies()

    assert len(collected.buckets) == 0
    assert len(collected.apps) == 0


def test_poks_install_with_global_poks_json(tmp_path: Path) -> None:
    global_content = {
        "buckets": [{"name": "global_bucket", "url": "https://github.com/global/bucket"}],
        "apps": [{"name": "global_app", "version": "1.0.0", "bucket": "global_bucket"}],
    }
    (tmp_path / "poks.json").write_text(json.dumps(global_content))

    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._collect_dependencies()

    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "global_bucket"

    assert len(collected.apps) == 1
    assert collected.apps[0].name == "global_app"
    assert collected.apps[0].version == "1.0.0"


def test_poks_install_merges_buckets_with_conflicts(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")

    from poks.domain import PoksBucket

    base = PoksConfig(buckets=[PoksBucket(name="main", url="https://github.com/example/main")], apps=[])
    duplicate = PoksConfig(buckets=[PoksBucket(name="main", url="https://github.com/different/main")], apps=[])

    poks_install._merge_buckets(base, duplicate.buckets)

    assert len(base.buckets) == 1
    assert base.buckets[0].url == "https://github.com/example/main"


def test_poks_install_run_with_no_dependencies(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")

    poks_install._collect_dependencies = MagicMock(return_value=PoksConfig())  # type: ignore

    assert poks_install.run() == 0
    poks_install._collect_dependencies.assert_called_once()


def test_poks_install_with_relative_install_dir(tmp_path: Path) -> None:
    """Test that PoksInstall uses relative install_dir from config and appends .poks."""
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    config = {"install_dir": "build/tools"}
    poks_install = PoksInstall(exec_context, "install", config)

    resolved_dir = poks_install._resolve_root_dir()

    assert resolved_dir == tmp_path / "build" / "tools" / ".poks"
    assert not resolved_dir.is_absolute() or resolved_dir.is_relative_to(tmp_path)


def test_poks_install_with_absolute_install_dir_raises(tmp_path: Path) -> None:
    """Test that PoksInstall raises exception when absolute path is provided."""
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    # Use a truly absolute path that works on both Unix and Windows
    absolute_path = str(Path.home() / "absolute" / "path" / "tools")
    config = {"install_dir": absolute_path}
    poks_install = PoksInstall(exec_context, "install", config)

    with pytest.raises(UserNotificationException, match=r"absolute.*path"):
        poks_install._resolve_root_dir()


def test_poks_install_without_config_uses_default(tmp_path: Path) -> None:
    """Test that PoksInstall uses default root_dir when no config provided."""
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")

    resolved_dir = poks_install._resolve_root_dir()

    assert resolved_dir == Path.home() / ".poks"


def test_poks_install_get_config(tmp_path: Path) -> None:
    """Test that get_config returns install_dir when configured."""
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    config = {"install_dir": "build/tools"}
    poks_install = PoksInstall(exec_context, "install", config)

    result = poks_install.get_config()

    assert result == {"install_dir": "build/tools"}


def test_poks_install_get_config_without_install_dir(tmp_path: Path) -> None:
    """Test that get_config returns None when no install_dir configured."""
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    poks_install = PoksInstall(exec_context, "install")

    result = poks_install.get_config()

    assert result is None
