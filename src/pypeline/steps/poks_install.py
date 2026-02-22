from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

from poks.domain import PoksApp, PoksBucket
from poks.domain import PoksConfig as _PoksConfig
from poks.poks import Poks
from py_app_dev.core.config import BaseConfigJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


@dataclass
class PoksInstallExecutionInfo(BaseConfigJSONMixin):
    install_dirs: list[Path] = field(default_factory=list)
    env_vars: dict[str, Any] = field(default_factory=dict)

    def to_json_file(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        super().to_json_file(file_path)


@dataclass
class PoksInstallConfig(BaseConfigJSONMixin):
    """Configuration for PoksInstall step."""

    #: Relative path from project root for poks installation directory (will have .poks appended)
    install_dir: Optional[str] = None


TContext = TypeVar("TContext", bound=ExecutionContext)


class PoksInstall(PipelineStep[TContext], Generic[TContext]):
    def __init__(self, execution_context: TContext, group_name: str, config: Optional[dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.execution_info = PoksInstallExecutionInfo()
        self.user_config = PoksInstallConfig.from_dict(config) if config else PoksInstallConfig()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_config(self) -> dict[str, str] | None:
        config: dict[str, str] = {}
        if self.user_config.install_dir:
            config["install_dir"] = self.user_config.install_dir
        return config if config else None

    @property
    def install_dirs(self) -> list[Path]:
        return self.execution_info.install_dirs

    @property
    def _execution_info_file(self) -> Path:
        """Tracks execution info (installed dirs, env vars)."""
        return self.output_dir / "poks_install_exec_info.json"

    @property
    def _output_config_file(self) -> Path:
        """Generated poks.json (output)."""
        return self.output_dir / "poks.json"

    @property
    def _source_config_file(self) -> Path:
        """Source poks.json. Override to customize."""
        return self.project_root_dir / "poks.json"

    def _resolve_root_dir(self) -> Path:
        """Resolve poks root directory from config or use default."""
        if self.user_config.install_dir:
            install_path = Path(self.user_config.install_dir)
            if install_path.is_absolute():
                raise UserNotificationException(f"install_dir must be a relative path, got absolute path: {self.user_config.install_dir}")
            return self.project_root_dir / self.user_config.install_dir / ".poks"

        # Default fallback
        return Path.home() / ".poks"

    def _collect_dependencies(self) -> _PoksConfig:
        """Collect Poks dependencies. Override to add additional sources."""
        collected = _PoksConfig()

        if self._source_config_file.exists():
            try:
                source_config = _PoksConfig.from_file(self._source_config_file)
                self._merge_buckets(collected, source_config.buckets)
                self._merge_apps(collected, source_config.apps)
            except Exception as e:
                self.logger.warning(f"Failed to parse source poks.json: {e}")

        return collected

    def _merge_buckets(self, target: _PoksConfig, source_buckets: list[PoksBucket]) -> None:
        """Merge buckets, handling conflicts when same name has different URLs."""
        for bucket in source_buckets:
            existing = next((b for b in target.buckets if b.name == bucket.name), None)

            if existing is None:
                target.buckets.append(bucket)
            elif existing.url != bucket.url:
                self.logger.warning(
                    f"Bucket '{bucket.name}' defined multiple times with different URLs:\n  Existing: {existing.url}\n  New: {bucket.url}\n  Keeping existing definition."
                )

    def _merge_apps(self, target: _PoksConfig, source_apps: list[PoksApp]) -> None:
        """Merge apps, avoiding duplicates."""
        for app in source_apps:
            if app not in target.apps:
                target.apps.append(app)

    def _generate_poks_config(self, config: _PoksConfig) -> None:
        """Generate poks.json file from collected dependencies."""
        if not config.buckets and not config.apps:
            self.logger.info("No Poks dependencies found. Skipping poks.json generation.")
            return

        self._output_config_file.parent.mkdir(parents=True, exist_ok=True)
        self._output_config_file.write_text(config.to_json_string())

        self.logger.info(f"Generated poks.json with {len(config.buckets)} buckets and {len(config.apps)} apps")

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")

        try:
            collected = self._collect_dependencies()

            self._generate_poks_config(collected)

            if not collected.apps:
                self.logger.info("No Poks dependencies to install.")
                return 0

            poks = Poks(root_dir=self._resolve_root_dir())
            result = poks.install(collected)

            self.logger.info("Installed apps:")
            for app in result.apps:
                self.logger.info(app.format_status())

            self.execution_info.install_dirs.extend(result.dirs)
            self.execution_info.env_vars.update(result.env)

            self.execution_info.to_json_file(self._execution_info_file)

        except Exception as e:
            raise UserNotificationException(f"Failed to install poks dependencies: {e}") from e

        return 0

    def get_inputs(self) -> list[Path]:
        inputs: list[Path] = []
        if self._source_config_file.exists():
            inputs.append(self._source_config_file)
        return inputs

    def get_outputs(self) -> list[Path]:
        outputs: list[Path] = [self._output_config_file, self._execution_info_file]
        if self.execution_info.install_dirs:
            outputs.extend(self.execution_info.install_dirs)
        return outputs

    def update_execution_context(self) -> None:
        if self._execution_info_file.exists():
            execution_info = PoksInstallExecutionInfo.from_json_file(self._execution_info_file)
            unique_paths = list(dict.fromkeys(execution_info.install_dirs))
            self.execution_context.add_install_dirs(unique_paths)
            if execution_info.env_vars:
                self.execution_context.add_env_vars(execution_info.env_vars)
