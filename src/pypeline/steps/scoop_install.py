import json
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from py_app_dev.core.config import BaseConfigJSONMixin
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
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Path | None = None

    @classmethod
    def from_file(cls, config_file: Path) -> "ScoopManifest":
        config_dict = cls.parse_to_dict(config_file)
        return cls.from_dict(config_dict)

    @staticmethod
    def parse_to_dict(config_file: Path) -> dict[str, Any]:
        try:
            with open(config_file) as fs:
                config_dict = json.loads(fs.read())
                config_dict["file"] = config_file
            return config_dict
        except json.JSONDecodeError as e:
            raise UserNotificationException(f"Failed parsing scoop manifest file '{config_file}'. \nError: {e}") from e


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

    def _collect_dependencies(self) -> ScoopManifest:
        """Collect Scoop dependencies. Override to add additional sources."""
        collected_manifest = ScoopManifest()

        if self._source_manifest_file.exists():
            source_manifest = ScoopManifest.from_file(self._source_manifest_file)
            self._merge_buckets(collected_manifest, source_manifest.buckets)
            self._merge_apps(collected_manifest, source_manifest.apps)

        return collected_manifest

    def _merge_buckets(self, target_manifest: ScoopManifest, source_buckets: list[ScoopFileElement]) -> None:
        """Merge buckets, handling conflicts when same name has different sources."""
        for bucket in source_buckets:
            existing_bucket = next((b for b in target_manifest.buckets if b.name == bucket.name), None)

            if existing_bucket is None:
                target_manifest.buckets.append(bucket)
            elif existing_bucket.source != bucket.source:
                self.logger.warning(
                    f"Bucket '{bucket.name}' defined multiple times with different sources:\n"
                    f"  Existing: {existing_bucket.source}\n"
                    f"  New: {bucket.source}\n"
                    f"  Keeping existing definition."
                )

    def _merge_apps(self, target_manifest: ScoopManifest, source_apps: list[ScoopFileElement]) -> None:
        """Merge apps, warning when the same app is declared with a different source or version."""
        for app in source_apps:
            existing_app = next((a for a in target_manifest.apps if a.name == app.name), None)

            if existing_app is None:
                target_manifest.apps.append(app)
            elif existing_app != app:
                self.logger.warning(
                    f"App '{app.name}' defined multiple times with different definitions:\n"
                    f"  Existing: source={existing_app.source}, version={existing_app.version}\n"
                    f"  New: source={app.source}, version={app.version}\n"
                    f"  Keeping existing definition."
                )

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

        collected_manifest = self._collect_dependencies()
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
        inputs: list[Path] = [package_version_file()]
        if self._source_manifest_file.exists():
            inputs.append(self._source_manifest_file)
        return inputs

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
