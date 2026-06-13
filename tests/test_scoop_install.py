import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.scoop_wrapper import InstalledScoopApp, ScoopFileElement, ScoopWrapper

from pypeline.domain.execution_context import ExecutionContext
from pypeline.main import package_version_file
from pypeline.steps.scoop_install import ScoopInstall, ScoopInstallExecutionInfo, ScoopManifest, ScoopManifestFile


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

    manifest_file = ScoopManifestFile.from_file(scoop_file)
    assert manifest_file.file == scoop_file

    manifest = manifest_file.payload
    assert len(manifest.buckets) == 2
    main_bucket = next((bucket for bucket in manifest.buckets if bucket.name == "main"), None)
    assert main_bucket is not None
    assert main_bucket.source == "https://github.com/ScoopInstaller/Main"

    extras_bucket = next((bucket for bucket in manifest.buckets if bucket.name == "extras"), None)
    assert extras_bucket is not None
    assert extras_bucket.source == "https://github.com/ScoopInstaller/Extras"

    assert len(manifest.apps) == 2
    git_app = next((app for app in manifest.apps if app.name == "git"), None)
    assert git_app is not None
    assert git_app.source == "main"
    assert git_app.version == "2.42.0"

    vscode_app = next((app for app in manifest.apps if app.name == "vscode"), None)
    assert vscode_app is not None
    assert vscode_app.source == "extras"
    assert vscode_app.version is None


def test_scoop_install_execution_info_serialization(tmp_path: Path) -> None:
    execution_info = ScoopInstallExecutionInfo(
        install_dirs=[tmp_path / "app1", tmp_path / "app2"],
        dependency_dirs=[tmp_path / "app3"],
        env_vars={"PATH": "/usr/bin", "EDITOR": "vim"},
    )

    info_file = tmp_path / "execution_info.json"
    execution_info.to_json_file(info_file)
    assert info_file.exists()

    loaded_info = ScoopInstallExecutionInfo.from_json_file(info_file)
    assert len(loaded_info.install_dirs) == 2
    assert tmp_path / "app1" in loaded_info.install_dirs
    assert tmp_path / "app2" in loaded_info.install_dirs
    assert loaded_info.dependency_dirs == [tmp_path / "app3"]
    assert loaded_info.env_vars["PATH"] == "/usr/bin"
    assert loaded_info.env_vars["EDITOR"] == "vim"


def test_scoop_install_with_no_dependencies(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")
    collected = scoop_install._merge_manifests()

    assert scoop_install._manifest_files == []
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
    collected = scoop_install._merge_manifests()

    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "global_bucket"
    assert collected.buckets[0].source == "https://github.com/global/bucket"

    assert len(collected.apps) == 1
    assert collected.apps[0].name == "global_app"
    assert collected.apps[0].version == "1.0.0"


def test_scoop_install_raises_on_corrupt_scoopfile(tmp_path: Path) -> None:
    (tmp_path / "scoopfile.json").write_text("{ this is not valid json")
    exec_context = ExecutionContext(project_root_dir=tmp_path)

    # Manifests are collected at construction time, so a corrupt file fails fast.
    with pytest.raises(UserNotificationException):
        ScoopInstall(exec_context, "install")


def test_scoop_install_merges_multiple_sources(tmp_path: Path) -> None:
    """A subclass appends manifest sources to the list; later sources override earlier ones by name."""
    source_content = {"buckets": [{"Name": "main", "Source": "https://github.com/ScoopInstaller/Main"}], "apps": [{"Name": "git", "Source": "main"}]}
    (tmp_path / "scoopfile.json").write_text(json.dumps(source_content))
    extra_manifest = tmp_path / "extra.json"
    extra_content = {
        "buckets": [{"Name": "main", "Source": "https://github.com/different/main"}, {"Name": "extras", "Source": "https://github.com/ScoopInstaller/Extras"}],
        "apps": [{"Name": "vscode", "Source": "extras"}],
    }
    extra_manifest.write_text(json.dumps(extra_content))

    class MultiSourceScoopInstall(ScoopInstall[ExecutionContext]):
        def _collect_manifests(self) -> list[ScoopManifestFile]:
            return [*super()._collect_manifests(), ScoopManifestFile.from_file(extra_manifest)]

    scoop_install = MultiSourceScoopInstall(ExecutionContext(project_root_dir=tmp_path), "install")
    collected = scoop_install._merge_manifests()

    assert {bucket.name for bucket in collected.buckets} == {"main", "extras"}
    assert {app.name for app in collected.apps} == {"git", "vscode"}
    # The extra manifest comes after the root scoopfile.json, so it overrides the "main" bucket.
    main_bucket = next(bucket for bucket in collected.buckets if bucket.name == "main")
    assert main_bucket.source == "https://github.com/different/main"


def test_scoop_install_get_inputs_includes_package_version_file(tmp_path: Path) -> None:
    (tmp_path / "scoopfile.json").write_text("{}")
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    inputs = scoop_install.get_inputs()

    # The package version file is always an input so the step re-runs on a pypeline upgrade.
    assert package_version_file() in inputs
    assert tmp_path / "scoopfile.json" in inputs


def test_scoop_install_get_inputs_includes_all_collected_manifest_files(tmp_path: Path) -> None:
    """Every collected manifest file is a cache input, so editing any of them re-runs the step."""
    (tmp_path / "scoopfile.json").write_text(json.dumps({"apps": [{"Name": "git", "Source": "main"}]}))
    extra_manifest = tmp_path / "extra.json"
    extra_manifest.write_text(json.dumps({"apps": [{"Name": "vscode", "Source": "extras"}]}))

    class MultiSourceScoopInstall(ScoopInstall[ExecutionContext]):
        def _collect_manifests(self) -> list[ScoopManifestFile]:
            return [*super()._collect_manifests(), ScoopManifestFile.from_file(extra_manifest)]

    scoop_install = MultiSourceScoopInstall(ExecutionContext(project_root_dir=tmp_path), "install")
    inputs = scoop_install.get_inputs()

    assert package_version_file() in inputs
    assert tmp_path / "scoopfile.json" in inputs
    assert extra_manifest in inputs


def test_scoop_install_run_skips_on_non_windows(tmp_path: Path) -> None:
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Linux"):
        assert scoop_install.run() == 0

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Darwin"):
        assert scoop_install.run() == 0


def test_scoop_install_propagates_install_dirs_and_env_vars(tmp_path: Path) -> None:
    """Installed apps' PATH directories and environment variables reach the execution context."""
    (tmp_path / "scoopfile.json").write_text(json.dumps({"apps": [{"Name": "compiler", "Source": "main"}]}))
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    app_root = tmp_path / "scoop" / "apps" / "compiler" / "current"
    installed_app = InstalledScoopApp(
        name="compiler",
        version="1.0.0",
        path=app_root,
        bin_dirs=[Path("bin")],
        env_add_path=[Path("lib")],
        env_vars={"COMPILER_ROOT": str(app_root)},
        manifest_file=tmp_path / "manifest.json",
    )
    wrapper = Mock(spec=ScoopWrapper)
    wrapper.install.return_value = [installed_app]

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Windows"):
        with patch("pypeline.steps.scoop_install.create_scoop_wrapper", return_value=wrapper):
            assert scoop_install.run() == 0

    scoop_install.update_execution_context()

    # bin_dirs and env_add_path are resolved against the app root and added to PATH.
    assert app_root / "bin" in exec_context.install_dirs
    assert app_root / "lib" in exec_context.install_dirs
    # Environment variables declared by the app are propagated too.
    assert exec_context.env_vars["COMPILER_ROOT"] == str(app_root)


def test_scoop_install_merges_sources_into_the_generated_manifest(tmp_path: Path) -> None:
    # Root scoopfile.json plus a manifest contributed by an earlier step through the data registry.
    root_content = {"buckets": [{"Name": "main", "Source": "https://github.com/ScoopInstaller/Main"}], "apps": [{"Name": "git", "Source": "main"}]}
    (tmp_path / "scoopfile.json").write_text(json.dumps(root_content))
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    overlay = ScoopManifestFile(
        payload=ScoopManifest(
            buckets=[ScoopFileElement.from_dict({"name": "main", "source": "https://github.com/different/main"})],
            apps=[ScoopFileElement.from_dict({"name": "vscode", "source": "extras"})],
        )
    )
    exec_context.data_registry.insert(overlay, provider="EarlierStep")
    scoop_install = ScoopInstall(exec_context, "install")

    wrapper = Mock(spec=ScoopWrapper)
    wrapper.install.return_value = []
    with patch("pypeline.steps.scoop_install.platform.system", return_value="Windows"):
        with patch("pypeline.steps.scoop_install.create_scoop_wrapper", return_value=wrapper):
            assert scoop_install.run() == 0

    # run() writes the merged manifest, then installs from it.
    wrapper.install.assert_called_once_with(scoop_install._output_manifest_file)
    generated = ScoopManifest.from_file(scoop_install._output_manifest_file)
    assert {app.name for app in generated.apps} == {"git", "vscode"}
    # The registry source comes after the root file, so its "main" bucket wins.
    assert next(bucket for bucket in generated.buckets if bucket.name == "main").source == "https://github.com/different/main"
    # scoopfile.json is JSON: no positions are tracked, so the output never carries a source location.
    assert "_source_location" not in scoop_install._output_manifest_file.read_text()


def test_scoop_install_tracks_app_dir_without_adding_to_path(tmp_path: Path) -> None:
    """
    Regression for #13: an env-var-only app (no PATH dirs) must still be tracked as an output.

    Its install directory is recorded so an out-of-band `scoop uninstall` is detected on the
    next run, but the app root must NOT be added to the execution context install dirs (PATH).
    """
    (tmp_path / "scoopfile.json").write_text(json.dumps({"apps": [{"Name": "mytool", "Source": "main"}]}))
    exec_context = ExecutionContext(project_root_dir=tmp_path)
    scoop_install = ScoopInstall(exec_context, "install")

    app_dir = tmp_path / "scoop" / "apps" / "mytool" / "current"
    installed_app = InstalledScoopApp(
        name="mytool",
        version="1.0.0",
        path=app_dir,
        bin_dirs=[],  # no bin directories
        env_add_path=[],  # no directories added to PATH
        env_vars={"MYTOOL_ROOT": str(app_dir)},
        manifest_file=tmp_path / "manifest.json",
    )
    wrapper = Mock(spec=ScoopWrapper)
    wrapper.install.return_value = [installed_app]

    with patch("pypeline.steps.scoop_install.platform.system", return_value="Windows"):
        with patch("pypeline.steps.scoop_install.create_scoop_wrapper", return_value=wrapper):
            assert scoop_install.run() == 0

    # The app root is tracked as an output, so removing it (uninstall) re-triggers the step.
    assert app_dir in scoop_install.get_outputs()
    # ...but it is not propagated as an install dir, so it never lands on PATH.
    scoop_install.update_execution_context()
    assert app_dir not in exec_context.install_dirs
