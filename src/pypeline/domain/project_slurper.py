from pathlib import Path
from typing import Optional

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from .artifacts import ProjectArtifactsLocator
from .config import PipelineConfig, ProjectConfig


class ProjectSlurper:
    def __init__(self, project_dir: Path, config_file: Optional[str] = None) -> None:
        self.logger = logger.bind()
        self.artifacts_locator = ProjectArtifactsLocator(project_dir, config_file)
        try:
            self.user_config: ProjectConfig = ProjectConfig.from_file(self.artifacts_locator.config_file)
        except FileNotFoundError:
            raise UserNotificationException(f"Project configuration file '{self.artifacts_locator.config_file}' not found.") from None
        self.pipeline: PipelineConfig = self.user_config.pipeline

    @property
    def project_dir(self) -> Path:
        return self.artifacts_locator.project_root_dir

    @property
    def project_config(self) -> ProjectConfig:
        return self.user_config
