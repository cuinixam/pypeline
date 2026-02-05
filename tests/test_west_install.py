import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from py_app_dev.core.data_registry import DataRegistry
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.west_install import (
    WestDependency,
    WestInstall,
    WestInstallConfig,
    WestInstallResult,
    WestManifest,
    WestManifestFile,
    WestRemote,
    WestWorkspaceDir,
)
from tests.conftest import assert_element_of_type

# ============================================================================
# WestRemote Tests
# ============================================================================


def test_west_remote_creation() -> None:
    remote = WestRemote(name="origin", url_base="https://github.com/org")
    assert remote.name == "origin"
    assert remote.url_base == "https://github.com/org"


def test_west_remote_to_dict() -> None:
    remote = WestRemote(name="origin", url_base="https://github.com/org")
    d = remote.to_dict()
    # url_base should be serialized with its field name (not alias)
    assert d["name"] == "origin"
    assert d["url_base"] == "https://github.com/org"


def test_west_remote_from_dict() -> None:
    # Note: uses 'url-base' alias for deserialization (as in west.yaml format)
    d = {"name": "origin", "url-base": "https://github.com/org"}
    remote = WestRemote.from_dict(d)
    assert remote.name == "origin"
    assert remote.url_base == "https://github.com/org"


# ============================================================================
# WestDependency Tests
# ============================================================================


def test_west_dependency_creation() -> None:
    dep = WestDependency(name="zephyr", remote="origin", revision="v3.2.0", path="modules/zephyr")
    assert dep.name == "zephyr"
    assert dep.remote == "origin"
    assert dep.revision == "v3.2.0"
    assert dep.path == "modules/zephyr"


def test_west_dependency_to_dict() -> None:
    dep = WestDependency(name="zephyr", remote="origin", revision="v3.2.0", path="modules/zephyr")
    d = dep.to_dict()
    assert d == {"name": "zephyr", "remote": "origin", "revision": "v3.2.0", "path": "modules/zephyr"}


def test_west_dependency_from_dict() -> None:
    d = {"name": "zephyr", "remote": "origin", "revision": "v3.2.0", "path": "modules/zephyr"}
    dep = WestDependency.from_dict(d)
    assert dep.name == "zephyr"
    assert dep.remote == "origin"
    assert dep.revision == "v3.2.0"
    assert dep.path == "modules/zephyr"


# ============================================================================
# WestManifest Tests
# ============================================================================


def test_west_manifest_defaults() -> None:
    manifest = WestManifest()
    assert manifest.remotes == []
    assert manifest.projects == []


def test_west_manifest_with_data() -> None:
    remote = WestRemote(name="origin", url_base="https://github.com/org")
    dep = WestDependency(name="zephyr", remote="origin", revision="v3.2.0", path="modules/zephyr")
    manifest = WestManifest(remotes=[remote], projects=[dep])

    assert len(manifest.remotes) == 1
    assert len(manifest.projects) == 1
    assert manifest.remotes[0].name == "origin"
    assert manifest.projects[0].name == "zephyr"


# ============================================================================
# WestManifestFile Tests
# ============================================================================


def test_west_manifest_file_from_file(tmp_path: Path) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: zephyr
      remote: origin
      revision: v3.2.0
      path: modules/zephyr
"""
    manifest_file = tmp_path / "west.yaml"
    manifest_file.write_text(manifest_content)

    west_manifest = WestManifestFile.from_file(manifest_file)

    assert west_manifest.file == manifest_file
    remote = assert_element_of_type(west_manifest.manifest.remotes, WestRemote)
    assert remote.name == "origin"
    assert remote.url_base == "https://github.com/org"
    dep = assert_element_of_type(west_manifest.manifest.projects, WestDependency)
    assert dep.name == "zephyr"
    assert dep.remote == "origin"
    assert dep.revision == "v3.2.0"
    assert dep.path == "modules/zephyr"


def test_west_manifest_file_parse_error(tmp_path: Path) -> None:
    manifest_file = tmp_path / "west.yaml"
    manifest_file.write_text("invalid: yaml: content: [")

    with pytest.raises(UserNotificationException, match="Failed scanning west manifest file"):
        WestManifestFile.from_file(manifest_file)


def test_west_manifest_file_from_file_with_multiple_dependencies(tmp_path: Path) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
    - name: nordic
      url-base: https://github.com/nordic
  projects:
    - name: zephyr
      remote: origin
      revision: v3.2.0
      path: modules/zephyr
    - name: sdk-nrf
      remote: nordic
      revision: v2.5.0
      path: modules/nrf
"""
    manifest_file = tmp_path / "west.yaml"
    manifest_file.write_text(manifest_content)

    west_manifest = WestManifestFile.from_file(manifest_file)

    assert len(west_manifest.manifest.remotes) == 2
    assert len(west_manifest.manifest.projects) == 2


# ============================================================================
# WestInstallResult Tests
# ============================================================================


def test_west_install_result_empty() -> None:
    result = WestInstallResult()
    assert result.installed_dirs == []


def test_west_install_result_with_dirs() -> None:
    dirs = [Path("/path/to/dep1"), Path("/path/to/dep2")]
    result = WestInstallResult(installed_dirs=dirs)
    assert result.installed_dirs == dirs


def test_west_install_result_to_json_string() -> None:
    dirs = [Path("/path/to/dep1"), Path("/path/to/dep2")]
    result = WestInstallResult(installed_dirs=dirs)
    json_str = result.to_json_string()

    parsed = json.loads(json_str)
    assert "installed_dirs" in parsed
    assert len(parsed["installed_dirs"]) == 2


def test_west_install_result_to_json_file(tmp_path: Path) -> None:
    dirs = [Path("/path/to/dep1"), Path("/path/to/dep2")]
    result = WestInstallResult(installed_dirs=dirs)

    result_file = tmp_path / "subdir" / "result.json"
    result.to_json_file(result_file)

    assert result_file.exists()
    parsed = json.loads(result_file.read_text())
    assert len(parsed["installed_dirs"]) == 2


def test_west_install_result_from_json_file(tmp_path: Path) -> None:
    result_file = tmp_path / "result.json"
    result_file.write_text('{"installed_dirs": ["/path/to/dep1", "/path/to/dep2"]}')

    result = WestInstallResult.from_json_file(result_file)

    assert len(result.installed_dirs) == 2
    assert result.installed_dirs[0] == Path("/path/to/dep1")


def test_west_install_result_from_json_file_invalid(tmp_path: Path) -> None:
    result_file = tmp_path / "result.json"
    result_file.write_text("invalid json")

    with pytest.raises(UserNotificationException):
        WestInstallResult.from_json_file(result_file)


# ============================================================================
# WestInstall Step Tests
# ============================================================================


@pytest.fixture
def west_execution_context(project: Path) -> Mock:
    """Fixture for WestInstall-specific execution context with data_registry."""
    context = Mock(spec=ExecutionContext)
    context.project_root_dir = project
    context.create_artifacts_locator.return_value = ProjectArtifactsLocator(project)
    context.data_registry = DataRegistry()
    context.user_config_files = []
    context.get_input.return_value = None
    return context


def test_west_install_get_name(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")
    assert step.get_name() == "WestInstall"


def test_west_install_no_manifests_skips(west_execution_context: Mock) -> None:
    """When no west.yaml exists and no manifests registered, step returns early."""
    step = WestInstall(west_execution_context, "group_name")
    result = step.run()

    assert result == 0
    west_execution_context.create_process_executor.assert_not_called()


def test_west_install_loads_source_manifest(west_execution_context: Mock) -> None:
    """WestInstall loads manifests from project root west.yaml."""
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: external/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    step = WestInstall(west_execution_context, "group_name")

    assert len(step._manifests) == 1
    assert len(step._manifests[0].projects) == 1
    assert step._manifests[0].projects[0].name == "dep1"


def test_west_install_output_manifest_file_path(west_execution_context: Mock) -> None:
    """Verify the output manifest file path is in the output directory."""
    step = WestInstall(west_execution_context, "group_name")

    assert step._output_manifest_file.name == "west.yaml"
    assert step.output_dir in step._output_manifest_file.parents or step._output_manifest_file.parent == step.output_dir


def test_west_install_result_file_path(west_execution_context: Mock) -> None:
    """Verify the result file path is in the output directory."""
    step = WestInstall(west_execution_context, "group_name")

    assert step._install_result_file.name == "west_install_result.json"
    assert step.output_dir in step._install_result_file.parents or step._install_result_file.parent == step.output_dir


def test_west_install_merge_manifests(west_execution_context: Mock) -> None:
    """
    Test that manifests are merged correctly.

    Note: Duplicates are detected by full object equality (all fields),
    not just by name. This means entries with same name but different
    values are treated as distinct.
    """
    step = WestInstall(west_execution_context, "group_name")

    # Identical remotes (same name AND url_base) - should dedupe
    remote1 = WestRemote(name="origin", url_base="https://github.com/org")
    remote2 = WestRemote(name="origin", url_base="https://github.com/org")  # true duplicate
    remote3 = WestRemote(name="secondary", url_base="https://github.com/sec")

    # Identical deps (same all fields) - should dedupe
    dep1 = WestDependency(name="dep1", remote="origin", revision="v1.0", path="deps/dep1")
    dep2 = WestDependency(name="dep1", remote="origin", revision="v1.0", path="deps/dep1")  # true duplicate
    dep3 = WestDependency(name="dep2", remote="secondary", revision="v1.0", path="deps/dep2")

    manifest1 = WestManifest(remotes=[remote1], projects=[dep1])
    manifest2 = WestManifest(remotes=[remote2, remote3], projects=[dep2, dep3])

    merged = step._do_merge_manifests([manifest1, manifest2])

    # True duplicates (identical objects) are removed
    assert len(merged.remotes) == 2
    assert merged.remotes[0].name == "origin"
    assert merged.remotes[0].url_base == "https://github.com/org"
    assert merged.remotes[1].name == "secondary"

    # True duplicates (identical objects) are removed
    assert len(merged.projects) == 2
    assert merged.projects[0].name == "dep1"
    assert merged.projects[0].revision == "v1.0"
    assert merged.projects[1].name == "dep2"


def test_west_install_write_manifest_generates_yaml(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")

    remote = WestRemote(name="origin", url_base="https://github.com/org")
    dep = WestDependency(name="dep1", remote="origin", revision="v1.0", path="deps/dep1")
    manifest = WestManifest(remotes=[remote], projects=[dep])

    step._write_west_manifest_file(manifest)

    output_file = step._output_manifest_file
    assert output_file.exists()

    import yaml

    parsed = yaml.safe_load(output_file.read_text())
    assert "manifest" in parsed
    assert len(parsed["manifest"]["remotes"]) == 1
    assert len(parsed["manifest"]["projects"]) == 1
    # Check url-base is converted back (not url_base)
    assert parsed["manifest"]["remotes"][0]["url-base"] == "https://github.com/org"


def test_west_install_write_manifest_skips_empty(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")
    manifest = WestManifest()

    step._write_west_manifest_file(manifest)

    # No file should be created for empty manifest
    assert not step._output_manifest_file.exists()


def test_west_install_run_with_manifest(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: external/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    # Mock the process executor
    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    result = step.run()

    assert result == 0
    # west init and west update should be called
    assert west_execution_context.create_process_executor.call_count == 2


def test_west_install_run_records_installed_directories(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    # Create the workspace directory and dependency directory (default is build_dir)
    artifacts_locator = ProjectArtifactsLocator(west_execution_context.project_root_dir)
    workspace_dir = artifacts_locator.build_dir
    dep_dir = workspace_dir / "dep1"
    dep_dir.mkdir(parents=True)

    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    step.run()

    assert workspace_dir in step.installed_dirs
    assert dep_dir in step.installed_dirs


def test_west_install_get_inputs_includes_source_manifest(west_execution_context: Mock) -> None:
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text("manifest: {remotes: [], projects: []}")

    step = WestInstall(west_execution_context, "group_name")
    inputs = step.get_inputs()

    assert manifest_file in inputs


def test_west_install_get_outputs(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")
    outputs = step.get_outputs()

    assert step._output_manifest_file in outputs
    assert step._install_result_file in outputs


def test_west_install_update_execution_context(west_execution_context: Mock) -> None:
    # Create result file with installed dirs
    step = WestInstall(west_execution_context, "group_name")
    step._install_result_file.parent.mkdir(parents=True, exist_ok=True)

    dirs = [Path("/path/to/lib1"), Path("/path/to/lib2")]
    result = WestInstallResult(installed_dirs=dirs)
    result.to_json_file(step._install_result_file)

    step.update_execution_context()

    west_execution_context.add_install_dirs.assert_called_once()
    call_args = west_execution_context.add_install_dirs.call_args[0][0]
    assert Path("/path/to/lib1") in call_args
    assert Path("/path/to/lib2") in call_args


def test_west_install_update_execution_context_no_file(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")
    step.update_execution_context()

    west_execution_context.add_install_dirs.assert_not_called()


def test_west_install_with_data_registry_manifest(west_execution_context: Mock) -> None:
    # Register a WestManifestFile in the data registry
    registered_manifest = WestManifestFile(
        manifest=WestManifest(
            remotes=[WestRemote(name="registry", url_base="https://registry.com")],
            projects=[WestDependency(name="reg-dep", remote="registry", revision="v1.0", path="deps/reg-dep")],
        )
    )
    west_execution_context.data_registry.insert(registered_manifest, provider="TestProvider")

    step = WestInstall(west_execution_context, "group_name")

    manifest = assert_element_of_type(step._manifests, WestManifest)
    assert manifest.projects[0].name == "reg-dep"


def test_west_install_merges_source_and_registry_manifests(west_execution_context: Mock) -> None:
    # Create source manifest
    manifest_content = """
manifest:
  remotes:
    - name: source
      url-base: https://source.com
  projects:
    - name: source-dep
      remote: source
      revision: v1.0.0
      path: deps/source-dep
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    # Register a WestManifestFile
    registered_manifest = WestManifestFile(
        manifest=WestManifest(
            remotes=[WestRemote(name="registry", url_base="https://registry.com")],
            projects=[WestDependency(name="reg-dep", remote="registry", revision="v1.0", path="deps/reg-dep")],
        )
    )
    west_execution_context.data_registry.insert(registered_manifest, provider="TestProvider")

    step = WestInstall(west_execution_context, "group_name")

    assert len(step._manifests) == 2


def test_west_install_run_failure_raises_exception(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: deps/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    # Mock the process executor to raise an exception
    mock_executor = Mock()
    mock_executor.execute.side_effect = Exception("west command failed")
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")

    with pytest.raises(UserNotificationException, match="Failed to initialize and update with west"):
        step.run()


def test_west_install_west_init_command(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: deps/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    step.run()

    # First call should be west init
    first_call = west_execution_context.create_process_executor.call_args_list[0]
    command = first_call[0][0]

    assert command[0] == "west"
    assert command[1] == "init"
    assert "-l" in command
    assert "--mf" in command


def test_west_install_west_update_command(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: deps/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    step.run()

    # Second call should be west update
    second_call = west_execution_context.create_process_executor.call_args_list[1]
    command = second_call[0][0]

    assert command == ["west", "update"]


def test_west_install_result_file_created_after_run(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: deps/dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    step.run()

    assert step._install_result_file.exists()


def test_west_install_duplicate_installed_dirs_removed(west_execution_context: Mock) -> None:
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: dep1
    - name: dep1-alias
      remote: origin
      revision: v1.0.0
      path: dep1
"""
    manifest_file = west_execution_context.project_root_dir / "west.yaml"
    manifest_file.write_text(manifest_content)

    # Create the workspace directory and dependency directory (default is build_dir)
    artifacts_locator = ProjectArtifactsLocator(west_execution_context.project_root_dir)
    workspace_dir = artifacts_locator.build_dir
    dep_dir = workspace_dir / "dep1"
    dep_dir.mkdir(parents=True)

    mock_executor = Mock()
    west_execution_context.create_process_executor.return_value = mock_executor

    step = WestInstall(west_execution_context, "group_name")
    step.run()

    # dep1 should appear only once
    dep1_count = sum(1 for d in step.installed_dirs if d == dep_dir)
    assert dep1_count == 1


def test_west_manifest_file_handles_malformed_yaml(tmp_path: Path) -> None:
    manifest_file = tmp_path / "west.yaml"
    # This has a colon inside an unquoted string which causes a parser error
    manifest_file.write_text("manifest:\n  key: value: error")

    with pytest.raises(UserNotificationException, match=r"Failed (scanning|parsing) west manifest file"):
        WestManifestFile.from_file(manifest_file)


# ============================================================================
# WestInstallConfig and WestWorkspaceDir Tests
# ============================================================================


def test_west_install_config_defaults() -> None:
    config = WestInstallConfig()
    assert config.workspace_dir is None


def test_west_install_config_from_dict() -> None:
    config = WestInstallConfig.from_dict({"workspace_dir": "external/deps"})
    assert config.workspace_dir == "external/deps"


def test_west_install_config_manifest_file_from_dict() -> None:
    config = WestInstallConfig.from_dict({"manifest_file": "deps/west.yaml"})
    assert config.manifest_file == "deps/west.yaml"


def test_west_install_config_both_options() -> None:
    config = WestInstallConfig.from_dict({"workspace_dir": "external/deps", "manifest_file": "deps/west.yaml"})
    assert config.workspace_dir == "external/deps"
    assert config.manifest_file == "deps/west.yaml"


def test_west_workspace_dir_creation() -> None:
    workspace = WestWorkspaceDir(path=Path("/custom/path"))
    assert workspace.path == Path("/custom/path")


def test_west_install_workspace_dir_from_config(west_execution_context: Mock) -> None:
    config = {"workspace_dir": "custom/workspace"}
    step = WestInstall(west_execution_context, "group_name", config)

    expected_path = west_execution_context.project_root_dir / "custom/workspace"
    assert step._west_workspace_dir == expected_path


def test_west_install_workspace_dir_from_data_registry(west_execution_context: Mock) -> None:
    custom_path = west_execution_context.project_root_dir / "registry/workspace"

    # Register workspace dir in data registry
    west_execution_context.data_registry.insert(WestWorkspaceDir(path=custom_path), provider="TestProvider")

    # Config also provides a workspace_dir, but registry should win
    config = {"workspace_dir": "config/workspace"}
    step = WestInstall(west_execution_context, "group_name", config)

    assert step._west_workspace_dir == custom_path


def test_west_install_workspace_dir_fallback_to_build_dir(west_execution_context: Mock) -> None:
    step = WestInstall(west_execution_context, "group_name")

    artifacts_locator = ProjectArtifactsLocator(west_execution_context.project_root_dir)
    assert step._west_workspace_dir == artifacts_locator.build_dir


def test_west_install_workspace_dir_registry_priority_over_config(west_execution_context: Mock) -> None:
    registry_path = west_execution_context.project_root_dir / "from_registry"
    config_path = "from_config"

    # Register in data registry
    west_execution_context.data_registry.insert(WestWorkspaceDir(path=registry_path), provider="TestProvider")

    config = {"workspace_dir": config_path}
    step = WestInstall(west_execution_context, "group_name", config)

    # Registry should win
    assert step._west_workspace_dir == registry_path
    assert step._west_workspace_dir != west_execution_context.project_root_dir / config_path


def test_west_install_manifest_file_from_config(west_execution_context: Mock) -> None:
    """Test that custom manifest file path from config is used."""
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: custom-dep
      remote: origin
      revision: v1.0.0
      path: deps/custom-dep
"""
    custom_manifest = west_execution_context.project_root_dir / "custom" / "west.yaml"
    custom_manifest.parent.mkdir(parents=True)
    custom_manifest.write_text(manifest_content)

    config = {"manifest_file": "custom/west.yaml"}
    step = WestInstall(west_execution_context, "group_name", config)

    assert step._source_manifest_file == custom_manifest
    assert len(step._manifests) == 1
    assert step._manifests[0].projects[0].name == "custom-dep"


def test_west_install_manifest_file_fallback_to_default(west_execution_context: Mock) -> None:
    """Test that default west.yaml in project root is used when no config."""
    step = WestInstall(west_execution_context, "group_name")

    expected_path = west_execution_context.project_root_dir / "west.yaml"
    assert step._source_manifest_file == expected_path


def test_west_install_get_config_includes_manifest_file(west_execution_context: Mock) -> None:
    """Test that get_config includes manifest_file when configured."""
    config = {"manifest_file": "deps/west.yaml", "workspace_dir": "external"}
    step = WestInstall(west_execution_context, "group_name", config)

    result = step.get_config()
    assert result is not None
    assert result["manifest_file"] == "deps/west.yaml"
    assert result["workspace_dir"] == "external"


def test_west_install_get_config_only_manifest_file(west_execution_context: Mock) -> None:
    """Test that get_config returns manifest_file when only it is configured."""
    config = {"manifest_file": "deps/west.yaml"}
    step = WestInstall(west_execution_context, "group_name", config)

    result = step.get_config()
    assert result is not None
    assert result["manifest_file"] == "deps/west.yaml"
    assert "workspace_dir" not in result


# ============================================================================
# Generic Execution Context Inheritance Tests
# ============================================================================


class CustomExecutionContext(ExecutionContext):
    """Custom execution context with additional attributes for testing generic inheritance."""

    def __init__(self, project_root_dir: Path, custom_attribute: str) -> None:
        super().__init__(project_root_dir)
        self.custom_attribute = custom_attribute


class CustomWestInstall(WestInstall[CustomExecutionContext]):
    """Subclass that uses a custom execution context type."""

    def _collect_manifests(self) -> list[WestManifestFile]:
        # Access the custom attribute - this verifies type safety
        _ = self.execution_context.custom_attribute
        return super()._collect_manifests()

    def get_custom_attribute(self) -> str:
        """Method that accesses the custom execution context attribute."""
        return self.execution_context.custom_attribute


def test_west_install_generic_inheritance_with_custom_context(tmp_path: Path) -> None:
    """Test that WestInstall can be subclassed with a custom ExecutionContext type."""
    custom_context = CustomExecutionContext(tmp_path, custom_attribute="test_value")

    step = CustomWestInstall(custom_context, "group_name")

    # Verify the custom attribute is accessible via the typed getter
    assert step.get_custom_attribute() == "test_value"
    # Verify the execution context is the same instance we passed in
    assert step.execution_context is custom_context


def test_west_install_generic_subclass_collect_manifests(tmp_path: Path) -> None:
    """Test that overridden _collect_manifests can access custom context attributes."""
    custom_context = CustomExecutionContext(tmp_path, custom_attribute="manifest_test")

    # Create a manifest file to be collected
    manifest_content = """
manifest:
  remotes:
    - name: origin
      url-base: https://github.com/org
  projects:
    - name: dep1
      remote: origin
      revision: v1.0.0
      path: deps/dep1
"""
    manifest_file = tmp_path / "west.yaml"
    manifest_file.write_text(manifest_content)

    step = CustomWestInstall(custom_context, "group_name")

    assert assert_element_of_type(step._manifests, WestManifest).projects[0].name == "dep1"
