import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from py_app_dev.core.scoop_wrapper import ScoopFileElement

from pypeline.domain.execution_context import ExecutionContext
from pypeline.main import package_version_file
from pypeline.steps.scoop_install import ScoopInstall, ScoopInstallExecutionInfo, ScoopManifest


def test_scoop_data() -> None:
    scoop_content = {
        "buckets": [{"Name": "my_bucket", "Source": "https://github.com/my/bucket"}],
        "apps": [
            {
                "Name": "app1",
                "Source": "my_bucket",
                "Version": "1.0.0",
            },
            {
                "name": "app2",
                "source": "my_bucket",
                "version": "2.0.0",
            },
        ],
    }
    content = ScoopManifest.from_dict(scoop_content)
    assert content.buckets[0].name == "my_bucket"
    assert {app.name for app in content.apps} == {"app1", "app2"}
    # Check serialization back to dict
    assert json.loads(content.to_json_string()) == scoop_content


def test_scoop_manifest_file_from_file(tmp_path: Path) -> None:
    scoop_content = {
        "buckets": [{"Name": "main", "Source": "https://github.com/ScoopInstaller/Main"}, {"Name": "extras", "Source": "https://github.com/ScoopInstaller/Extras"}],
        "apps": [{"Name": "git", "Source": "main", "Version": "2.42.0"}, {"Name": "vscode", "Source": "extras"}],
    }

    scoop_file = tmp_path / "scoopfile.json"
    scoop_file.write_text(json.dumps(scoop_content, indent=2))

    manifest_file = ScoopManifest.from_file(scoop_file)
    assert manifest_file.file == scoop_file

    assert len(manifest_file.buckets) == 2
    main_bucket = next((bucket for bucket in manifest_file.buckets if bucket.name == "main"), None)
    assert main_bucket is not None
    assert main_bucket.source == "https://github.com/ScoopInstaller/Main"

    extras_bucket = next((bucket for bucket in manifest_file.buckets if bucket.name == "extras"), None)
    assert extras_bucket is not None
    assert extras_bucket.source == "https://github.com/ScoopInstaller/Extras"

    assert len(manifest_file.apps) == 2
    git_app = next((app for app in manifest_file.apps if app.name == "git"), None)
    assert git_app is not None
    assert git_app.source == "main"
    assert git_app.version == "2.42.0"

    vscode_app = next((app for app in manifest_file.apps if app.name == "vscode"), None)
    assert vscode_app is not None
    assert vscode_app.source == "extras"
    assert vscode_app.version is None


def test_scoop_install_execution_info_serialization(tmp_path: Path) -> None:
    execution_info = ScoopInstallExecutionInfo(install_dirs=[tmp_path / "app1", tmp_path / "app2"], env_vars={"PATH": "/usr/bin", "EDITOR": "vim"})

    info_file = tmp_path / "execution_info.json"
    execution_info.to_json_file(info_file)
    assert info_file.exists()

    loaded_info = ScoopInstallExecutionInfo.from_json_file(info_file)
    assert len(loaded_info.install_dirs) == 2
    assert tmp_path / "app1" in loaded_info.install_dirs
    assert tmp_path / "app2" in loaded_info.install_dirs
    assert loaded_info.env_vars["PATH"] == "/usr/bin"
    assert loaded_info.env_vars["EDITOR"] == "vim"


def test_scoop_install_with_no_dependencies(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")
    collected = scoop_install._collect_dependencies()

    assert len(collected.buckets) == 0
    assert len(collected.apps) == 0


def test_scoop_install_with_global_scoopfile(tmp_path: Path) -> None:
    global_scoop_content = {
        "buckets": [{"Name": "global_bucket", "Source": "https://github.com/global/bucket"}],
        "apps": [{"Name": "global_app", "Source": "global_bucket", "Version": "1.0.0"}],
    }
    (tmp_path / "scoopfile.json").write_text(json.dumps(global_scoop_content, indent=2))

    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")
    collected = scoop_install._collect_dependencies()

    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "global_bucket"
    assert collected.buckets[0].source == "https://github.com/global/bucket"

    assert len(collected.apps) == 1
    assert collected.apps[0].name == "global_app"
    assert collected.apps[0].version == "1.0.0"


def test_scoop_install_merges_buckets_with_conflicts(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    manifest = ScoopManifest(
        buckets=[ScoopFileElement.from_dict({"name": "main", "source": "https://github.com/ScoopInstaller/Main"})],
        apps=[],
    )
    duplicate = ScoopManifest(
        buckets=[ScoopFileElement.from_dict({"name": "main", "source": "https://github.com/different/main"})],
        apps=[],
    )

    scoop_install._merge_buckets(manifest, duplicate.buckets)

    assert len(manifest.buckets) == 1
    assert manifest.buckets[0].source == "https://github.com/ScoopInstaller/Main"


def test_scoop_install_merges_apps_avoids_duplicates(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    target = ScoopManifest(apps=[ScoopFileElement.from_dict({"name": "git", "source": "main", "version": "2.42.0"})])
    source_apps = [
        ScoopFileElement.from_dict({"name": "git", "source": "main", "version": "2.42.0"}),
        ScoopFileElement.from_dict({"name": "vscode", "source": "extras"}),
    ]

    scoop_install._merge_apps(target, source_apps)

    assert {app.name for app in target.apps} == {"git", "vscode"}


def test_scoop_install_get_inputs_includes_package_version_file(tmp_path: Path) -> None:
    (tmp_path / "scoopfile.json").write_text("{}")
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    inputs = scoop_install.get_inputs()

    # The package version file is always an input so the step re-runs on a pypeline upgrade.
    assert package_version_file() in inputs
    assert tmp_path / "scoopfile.json" in inputs


def test_scoop_install_run_skips_on_non_windows(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Linux"):
        assert scoop_install.run() == 0

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Darwin"):
        assert scoop_install.run() == 0


def test_scoop_install_run_executes_on_windows(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    scoop_install._collect_dependencies = MagicMock(return_value=ScoopManifest())  # type: ignore

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Windows"):
        assert scoop_install.run() == 0
        scoop_install._collect_dependencies.assert_called_once()
