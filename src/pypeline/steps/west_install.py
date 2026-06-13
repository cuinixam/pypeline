import hashlib
import io
import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

import yaml
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from py_app_dev.core.config import ConfigElement, ConfigFile, merge_named_elements
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep
from ..main import package_version_file


@dataclass
class WestDependency(ConfigElement):
    #: Project name
    name: str
    #: Remote name
    remote: str
    #: Revision (tag, branch, or commit)
    revision: str
    #: Path where the dependency will be installed
    path: str
    #: Clone depth for shallow clones (optional, west native support)
    clone_depth: int | None = field(default=None, metadata={"alias": "clone-depth"})


@dataclass
class WestRemote(ConfigElement):
    #: Remote name
    name: str
    #: URL base
    url_base: str = field(metadata={"alias": "url-base"})


@dataclass
class WestManifest(ConfigElement):
    #: Remote configurations
    remotes: list[WestRemote] = field(default_factory=list)
    #: Project dependencies
    projects: list[WestDependency] = field(default_factory=list)


class WestManifestFile(ConfigFile[WestManifest]):
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WestManifestFile":
        # The west.yaml wire format nests the payload under a top-level "manifest" key.
        if "manifest" not in data:
            raise UserNotificationException("West manifest is missing the 'manifest' key.")
        return cls(payload=WestManifest.from_dict(data["manifest"]))


@dataclass
class WestInstallResult(DataClassJSONMixin):
    """Tracks paths of installed west dependencies."""

    installed_dirs: list[Path] = field(default_factory=list)

    class Config(BaseConfig):
        """Mashumaro configuration for JSON serialization."""

        omit_none = True

    @classmethod
    def from_json_file(cls, file_path: Path) -> "WestInstallResult":
        try:
            result = cls.from_dict(json.loads(file_path.read_text()))
        except Exception as e:
            output = io.StringIO()
            traceback.print_exc(file=output)
            raise UserNotificationException(output.getvalue()) from e
        return result

    def to_json_string(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_json_file(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json_string())


@dataclass
class WestWorkspaceDir:
    """West workspace directory path for data registry sharing."""

    path: Path


@dataclass
class WestInstallConfig(DataClassJSONMixin):
    """Configuration for WestInstall step."""

    #: Relative path from project root for west workspace directory
    workspace_dir: str | None = None
    #: Relative path from project root to west manifest file (defaults to west.yaml)
    manifest_file: str | None = None


TContext = TypeVar("TContext", bound=ExecutionContext)


class WestInstall(PipelineStep[TContext], Generic[TContext]):
    def __init__(self, execution_context: TContext, group_name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.install_result = WestInstallResult()
        self.user_config = WestInstallConfig.from_dict(config) if config else WestInstallConfig()

        self._west_workspace_dir = self._resolve_workspace_dir()
        self._manifest_files = self._collect_manifests()

    @property
    def _manifests(self) -> list[WestManifest]:
        return [manifest_file.payload for manifest_file in self._manifest_files]

    def _resolve_workspace_dir(self) -> Path:
        """Resolve workspace directory from data registry (priority) or config."""
        # Check data registry first (highest priority)
        registry_entries = self.execution_context.data_registry.find_data(WestWorkspaceDir)
        if registry_entries:
            return registry_entries[0].path

        # Check config
        if self.user_config.workspace_dir:
            return self.project_root_dir / self.user_config.workspace_dir

        # Fallback to build dir
        return self.execution_context.create_artifacts_locator().build_dir

    def _collect_manifests(self) -> list[WestManifestFile]:
        """Collect manifest sources in override order: a later source overrides an earlier one. Override to add additional sources."""
        manifests: list[WestManifestFile] = []
        if self._source_manifest_file.exists():
            manifests.append(WestManifestFile.from_file(self._source_manifest_file))
        manifests.extend(self.execution_context.data_registry.find_data(WestManifestFile))
        return manifests

    @property
    def _source_manifest_file(self) -> Path:
        """Source manifest file path. Uses configured path or defaults to west.yaml in project root."""
        if self.user_config.manifest_file:
            return self.project_root_dir / self.user_config.manifest_file
        return self.project_root_dir / "west.yaml"

    @property
    def _output_manifest_file(self) -> Path:
        """Generated west.yaml (output)."""
        return self.output_dir / "west.yaml"

    @property
    def _install_result_file(self) -> Path:
        """Tracks installed dependency directories."""
        return self.output_dir / "west_install_result.json"

    @property
    def installed_dirs(self) -> list[Path]:
        return self.install_result.installed_dirs

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_id(self) -> str:
        """Return unique identifier for dependency tracking (.deps.json filename)."""
        if self.user_config.manifest_file:
            manifest_hash = hashlib.md5(self.user_config.manifest_file.encode(), usedforsecurity=False).hexdigest()[:8]
            return f"{self.get_name()}_{manifest_hash}"
        return self.get_name()

    def get_config(self) -> dict[str, str] | None:
        config: dict[str, str] = {}
        if self.user_config.workspace_dir:
            config["workspace_dir"] = self.user_config.workspace_dir
        if self.user_config.manifest_file:
            config["manifest_file"] = self.user_config.manifest_file
        return config if config else None

    def _merge_manifests(self) -> WestManifest:
        return self._do_merge_manifests(self._manifests)

    def _do_merge_manifests(self, manifests: list[WestManifest]) -> WestManifest:
        """Merge multiple manifests in list order; a later definition with the same name overrides the earlier one."""
        merged = WestManifest()
        for manifest in manifests:
            merge_named_elements(merged.remotes, manifest.remotes)
            merge_named_elements(merged.projects, manifest.projects)
        return merged

    def _write_west_manifest_file(self, manifest: WestManifest) -> None:
        """Write merged manifest to west.yaml file."""
        if not manifest.remotes and not manifest.projects:
            self.logger.info("No West dependencies found. Skipping west.yaml generation.")
            return

        west_config = {"manifest": manifest.to_dict()}

        self._output_manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._output_manifest_file, "w") as f:
            yaml.dump(west_config, f, default_flow_style=False)

        self.logger.info(f"Generated west.yaml with {len(manifest.projects)} dependencies")

    def _run_west_init(self) -> None:
        """Initialize west workspace."""
        self.execution_context.create_process_executor(
            [
                "west",
                "init",
                "-l",
                "--mf",
                self._output_manifest_file.as_posix(),
                self._west_workspace_dir.joinpath("do_not_care").as_posix(),
            ],
            cwd=self.project_root_dir,
        ).execute()

    def _run_west_update(self) -> None:
        """Update/download dependencies."""
        self.execution_context.create_process_executor(
            ["west", "update"],
            cwd=self._west_workspace_dir,
        ).execute()

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")

        try:
            merged_manifest = self._merge_manifests()
            self._write_west_manifest_file(merged_manifest)

            if not merged_manifest.projects:
                self.logger.info("No West dependencies to install.")
                return 0

            self._run_west_init()
            self._run_west_update()
            self._record_installed_directories(merged_manifest)
            self.install_result.to_json_file(self._install_result_file)

        except Exception as e:
            raise UserNotificationException(f"Failed to initialize and update with west: {e}") from e

        return 0

    def _record_installed_directories(self, manifest: WestManifest) -> None:
        """Record directories created by west."""
        dirs: list[Path] = []

        if self._west_workspace_dir.exists():
            dirs.append(self._west_workspace_dir)

        for project in manifest.projects:
            dep_dir = self._west_workspace_dir / project.path
            if dep_dir.exists():
                dirs.append(dep_dir)
                self.logger.debug(f"Tracked dependency directory: {dep_dir}")

        self.install_result.installed_dirs = list(dict.fromkeys(dirs))

    def get_inputs(self) -> list[Path]:
        # The package version file re-runs the step on a pypeline upgrade: the west step's own
        # merge/generation/orchestration is pypeline code, so a fix there must invalidate the cache.
        inputs: list[Path] = [package_version_file()]
        inputs.extend(manifest_file.file for manifest_file in self._manifest_files if manifest_file.file and manifest_file.file.exists())
        return list(dict.fromkeys(inputs))

    def get_outputs(self) -> list[Path]:
        outputs: list[Path] = [self._output_manifest_file, self._install_result_file]
        if self.install_result.installed_dirs:
            outputs.extend(self.install_result.installed_dirs)
        elif self._manifest_files:
            outputs.append(self._west_workspace_dir)
        return outputs

    def update_execution_context(self) -> None:
        if self._install_result_file.exists():
            result = WestInstallResult.from_json_file(self._install_result_file)
            if result.installed_dirs:
                unique_paths = list(dict.fromkeys(result.installed_dirs))
                self.execution_context.add_install_dirs(unique_paths)
