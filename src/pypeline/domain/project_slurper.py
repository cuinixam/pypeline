from pathlib import Path

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from .artifacts import ProjectArtifactsLocator
from .config import PipelineConfig, ProjectConfig


class ProjectSlurper:
    def __init__(self, project_dir: Path) -> None:
        self.logger = logger.bind()
        self.artifacts_locator = ProjectArtifactsLocator(project_dir)
        try:
            self.user_config: ProjectConfig = ProjectConfig.from_file(self.artifacts_locator.config_file)
        except FileNotFoundError:
            raise UserNotificationException(f"Project configuration file '{self.artifacts_locator.config_file}' not found.") from None
        self.pipeline: PipelineConfig = self.user_config.pipeline

    @property
    def project_dir(self) -> Path:
        return self.artifacts_locator.project_root_dir
