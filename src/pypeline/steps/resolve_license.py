import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.config import BaseConfigJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


@dataclass
class ResolveLicenseExecutionInfo(BaseConfigJSONMixin):
    env_vars: Dict[str, Any] = field(default_factory=dict)

    def to_json_file(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        super().to_json_file(file_path)


@dataclass
class ResolveLicenseConfig(BaseConfigJSONMixin):
    license_config: str = "license_servers.json"


class ResolveLicenseServer(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: Optional[str], config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.user_config = ResolveLicenseConfig.from_dict(config) if config else ResolveLicenseConfig()
        self.execution_info = ResolveLicenseExecutionInfo()

    @property
    def _license_config_file(self) -> Path:
        return self.execution_context.project_root_dir / self.user_config.license_config

    @property
    def _execution_info_file(self) -> Path:
        return self.output_dir / "resolve_license_exec_info.json"

    def _detect_timezone(self) -> str:
        return time.tzname[0]

    def _resolve_site(self, timezones: Dict[str, List[str]], tz_name: str) -> Optional[str]:
        for site, tz_names in timezones.items():
            if tz_name in tz_names:
                return site
        return None

    def run(self) -> int:
        if not self._license_config_file.exists():
            raise UserNotificationException(f"License config file not found: {self._license_config_file}")

        with self._license_config_file.open("r") as f:
            license_config = json.load(f)

        tz_name = self._detect_timezone()
        logger.info(f"Detected timezone: {tz_name}")

        timezones: Dict[str, List[str]] = license_config.get("timezones", {})
        servers: Dict[str, Dict[str, Any]] = license_config.get("servers", {})

        site = self._resolve_site(timezones, tz_name)

        if site:
            logger.info(f"Matched site: {site}")
        else:
            if "default" in servers:
                site = "default"
                logger.info(f"No site matched for timezone '{tz_name}', using default")
            else:
                raise UserNotificationException(
                    f"No license server configured for timezone '{tz_name}' and no default configured in {self._license_config_file}"
                )

        env_vars = servers.get(site, {})
        if not env_vars:
            raise UserNotificationException(f"No server configuration found for site '{site}' in {self._license_config_file}")

        self.execution_info.env_vars.update(env_vars)
        self.execution_info.to_json_file(self._execution_info_file)
        self.execution_context.add_env_vars(env_vars)

        for key, value in env_vars.items():
            logger.info(f"Set {key}={value}")

        return 0

    def get_inputs(self) -> List[Path]:
        if self._license_config_file.exists():
            return [self._license_config_file]
        return []

    def get_outputs(self) -> List[Path]:
        return [self._execution_info_file]

    def get_name(self) -> str:
        return self.__class__.__name__

    def update_execution_context(self) -> None:
        if self._execution_info_file.exists():
            execution_info = ResolveLicenseExecutionInfo.from_json_file(self._execution_info_file)
            if execution_info.env_vars:
                self.execution_context.add_env_vars(execution_info.env_vars)
