import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from py_app_dev.core.config import BaseConfigJSONMixin, ConfigFile, merge_named_elements
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.core.scoop_wrapper import ScoopFileElement, ScoopWrapper

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep
from ..main import package_version_file


@dataclass
class ScoopManifest(BaseConfigJSONMixin):
    #: Scoop buckets
    buckets: list[ScoopFileElement] = field(default_factory=list)
    #: Scoop applications
    apps: list[ScoopFileElement] = field(default_factory=list)


class ScoopManifestFile(ConfigFile[ScoopManifest]):
    pass


@dataclass
class ScoopInstallExecutionInfo(BaseConfigJSONMixin):
    #: Directories that are added to PATH for subsequent steps (bin dirs + env_add_path).
    install_dirs: list[Path] = field(default_factory=list)
    #: Root directory of every installed app. Tracked only to detect out-of-band uninstalls
    #: (an app with no bin/env_add_path would otherwise leave nothing to check). NOT added to PATH.
    dependency_dirs: list[Path] = field(default_factory=list)
    env_vars: dict[str, Any] = field(default_factory=dict)

    def to_json_file(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        super().to_json_file(file_path)


def create_scoop_wrapper() -> ScoopWrapper:
    return ScoopWrapper()


TContext = TypeVar("TContext", bound=ExecutionContext)


class ScoopInstall(PipelineStep[TContext], Generic[TContext]):
    def __init__(self, execution_context: TContext, group_name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.execution_info = ScoopInstallExecutionInfo()
        self._manifest_files = self._collect_manifests()

    def get_name(self) -> str:
        return self.__class__.__name__

    @property
    def install_dirs(self) -> list[Path]:
        return self.execution_info.install_dirs

    @property
    def _execution_info_file(self) -> Path:
        """Tracks execution info (installed dirs, env vars)."""
        return self.output_dir / "scoop_install_exec_info.json"

    @property
    def _output_manifest_file(self) -> Path:
        """Generated scoopfile.json (output)."""
        return self.output_dir / "scoopfile.json"

    @property
    def _source_manifest_file(self) -> Path:
        """Source scoopfile.json. Override to customize."""
        return self.project_root_dir / "scoopfile.json"

    def _collect_manifests(self) -> list[ScoopManifestFile]:
        """
        Collect manifest sources in override order: a later source overrides an earlier one. Override to add additional sources.

        Called during __init__; overrides must not rely on subclass state initialized after super().__init__().
        """
        manifests: list[ScoopManifestFile] = []
        if self._source_manifest_file.exists():
            manifests.append(ScoopManifestFile.from_file(self._source_manifest_file))
        manifests.extend(self.execution_context.data_registry.find_data(ScoopManifestFile))
        return manifests

    def _merge_manifests(self) -> ScoopManifest:
        """Merge the collected manifests in list order; a later definition with the same name overrides the earlier one."""
        merged = ScoopManifest()
        for manifest_file in self._manifest_files:
            merge_named_elements(merged.buckets, manifest_file.payload.buckets)
            merge_named_elements(merged.apps, manifest_file.payload.apps)
        return merged

    def _generate_scoop_manifest(self, manifest: ScoopManifest) -> None:
        """Generate scoopfile.json file from collected dependencies."""
        if not manifest.buckets and not manifest.apps:
            self.logger.info("No Scoop dependencies found. Skipping scoopfile.json generation.")
            return

        self._output_manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self._output_manifest_file.write_text(manifest.to_json_string())

        self.logger.info(f"Generated scoopfile.json with {len(manifest.buckets)} buckets and {len(manifest.apps)} apps")

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")

        if platform.system() != "Windows":
            self.logger.warning(f"ScoopInstall step is only supported on Windows. Skipping. Current platform: {platform.system()}")
            return 0

        collected_manifest = self._merge_manifests()
        self._generate_scoop_manifest(collected_manifest)

        if not collected_manifest.apps:
            self.logger.info("No Scoop dependencies to install.")
            return 0

        try:
            installed_apps = create_scoop_wrapper().install(self._output_manifest_file)
        except Exception as e:
            raise UserNotificationException(f"Failed to install scoop dependencies: {e}") from e

        self.logger.debug("Installed apps:")
        for app in installed_apps:
            self.logger.debug(f" - {app.name} ({app.version})")
            self.execution_info.install_dirs.extend(app.get_all_required_paths())
            # Track the app root so an out-of-band `scoop uninstall` is detected on the next run,
            # even when the app contributes no PATH directories (e.g. an env-var-only tool).
            self.execution_info.dependency_dirs.append(app.path)
            self.execution_info.env_vars.update(app.env_vars)

        self.execution_info.to_json_file(self._execution_info_file)

        return 0

    def get_inputs(self) -> list[Path]:
        # The package version file makes the step re-run on a pypeline upgrade (the install logic ships with pypeline).
        inputs: list[Path] = [package_version_file()]
        inputs.extend(manifest_file.file for manifest_file in self._manifest_files if manifest_file.file and manifest_file.file.exists())
        return list(dict.fromkeys(inputs))

    def get_outputs(self) -> list[Path]:
        outputs: list[Path] = [self._output_manifest_file, self._execution_info_file]
        outputs.extend(self.execution_info.install_dirs)
        # Tracked so the step re-runs if any installed app directory is removed (e.g. uninstalled).
        outputs.extend(self.execution_info.dependency_dirs)
        return outputs

    def update_execution_context(self) -> None:
        if self._execution_info_file.exists():
            execution_info = ScoopInstallExecutionInfo.from_json_file(self._execution_info_file)
            unique_paths = list(dict.fromkeys(execution_info.install_dirs))
            self.execution_context.add_install_dirs(unique_paths)
            if execution_info.env_vars:
                self.execution_context.add_env_vars(execution_info.env_vars)
