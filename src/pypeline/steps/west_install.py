import io
import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from py_app_dev.core.config import BaseConfigDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


class BaseConfigJSONMixin(DataClassJSONMixin):
    class Config(BaseConfig):
        """Mashumaro configuration for JSON serialization."""

        omit_none = True
        serialize_by_alias = True

    def to_json_string(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_json_file(self, file_path: Path) -> None:
        file_path.write_text(self.to_json_string())


@dataclass
class WestDependency(BaseConfigDictMixin):
    #: Project name
    name: str
    #: Remote name
    remote: str
    #: Revision (tag, branch, or commit)
    revision: str
    #: Path where the dependency will be installed
    path: str


@dataclass
class WestRemote(BaseConfigDictMixin):
    #: Remote name
    name: str
    #: URL base
    url_base: str = field(metadata={"alias": "url-base"})


@dataclass
class WestManifest(BaseConfigDictMixin):
    #: Remote configurations
    remotes: list[WestRemote] = field(default_factory=list)
    #: Project dependencies
    projects: list[WestDependency] = field(default_factory=list)


@dataclass
class WestManifestFile(BaseConfigDictMixin):
    manifest: WestManifest
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Optional[Path] = None

    @classmethod
    def from_file(cls, config_file: Path) -> "WestManifestFile":
        config_dict = cls.parse_to_dict(config_file)
        return cls.from_dict(config_dict)

    @staticmethod
    def parse_to_dict(config_file: Path) -> dict[str, Any]:
        try:
            with open(config_file) as fs:
                config_dict = yaml.safe_load(fs)
                # Add file name to config to keep track of where configuration was loaded from
                config_dict["file"] = config_file
            return config_dict
        except ScannerError as e:
            raise UserNotificationException(f"Failed scanning west manifest file '{config_file}'. \nError: {e}") from e
        except ParserError as e:
            raise UserNotificationException(f"Failed parsing west manifest file '{config_file}'. \nError: {e}") from e


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
    workspace_dir: Optional[str] = None


class WestInstall(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.install_result = WestInstallResult()
        self.user_config = WestInstallConfig.from_dict(config) if config else WestInstallConfig()

        self._west_workspace_dir = self._resolve_workspace_dir()
        self._manifests = self._collect_manifests()

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
        manifests: list[WestManifestFile] = []

        if self._source_manifest_file.exists():
            try:
                manifests.append(WestManifestFile.from_file(self._source_manifest_file))
            except Exception as e:
                self.logger.warning(f"Failed to parse source west.yaml: {e}")

        # Check if there are registered manifests in the execution context data registry
        manifests.extend(self.execution_context.data_registry.find_data(WestManifestFile))
        return manifests

    @property
    def _source_manifest_file(self) -> Path:
        """Optional west.yaml in project root (input)."""
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

    def get_config(self) -> dict[str, str] | None:
        if self.user_config.workspace_dir:
            return {"workspace_dir": self.user_config.workspace_dir}
        return None

    def _merge_manifests(self, manifests: list[WestManifest]) -> WestManifest:
        """Merge multiple manifests, preserving order. First occurrence wins."""
        merged = WestManifest()
        for manifest in manifests:
            for remote in manifest.remotes:
                if remote not in merged.remotes:
                    merged.remotes.append(remote)
            for project in manifest.projects:
                if project not in merged.projects:
                    merged.projects.append(project)
        return merged

    def _write_west_manifest_file(self, manifest: WestManifest) -> None:
        """Write merged manifest to west.yaml file."""
        if not manifest.remotes and not manifest.projects:
            self.logger.info("No West dependencies found. Skipping west.yaml generation.")
            return

        west_config = {
            "manifest": {
                "remotes": [remote.to_dict() for remote in manifest.remotes],
                "projects": [project.to_dict() for project in manifest.projects],
            }
        }

        # Convert url_base back to url-base for west compatibility
        for remote in west_config["manifest"]["remotes"]:
            if "url_base" in remote:
                remote["url-base"] = remote.pop("url_base")

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
            merged_manifest = self._merge_manifests([mf.manifest for mf in self._manifests])
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
        inputs: list[Path] = []
        for manifest_file in self._manifests:
            if manifest_file.file and manifest_file.file.exists():
                inputs.append(manifest_file.file)
        return inputs

    def get_outputs(self) -> list[Path]:
        outputs: list[Path] = [self._output_manifest_file, self._install_result_file]
        if self.install_result.installed_dirs:
            outputs.extend(self.install_result.installed_dirs)
        elif self._manifests:
            outputs.append(self._west_workspace_dir)
        return outputs

    def update_execution_context(self) -> None:
        if self._install_result_file.exists():
            result = WestInstallResult.from_json_file(self._install_result_file)
            if result.installed_dirs:
                unique_paths = list(dict.fromkeys(result.installed_dirs))
                self.execution_context.add_install_dirs(unique_paths)
