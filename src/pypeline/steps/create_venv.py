from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep

DEFAULT_BOOTSTRAP_SCRIPT = "bootstrap.py"


@dataclass
class CreateVEnvConfig(DataClassDictMixin):
    bootstrap_script: str = DEFAULT_BOOTSTRAP_SCRIPT


class CreateVEnv(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    @property
    def install_dirs(self) -> List[Path]:
        return [self.project_root_dir / dir for dir in [".venv/Scripts", ".venv/bin"] if (self.project_root_dir / dir).exists()]

    def get_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")
        config = CreateVEnvConfig.from_dict(self.config) if self.config else CreateVEnvConfig()
        bootstrap_script = self.project_root_dir / config.bootstrap_script
        if not bootstrap_script.exists():
            if config.bootstrap_script == DEFAULT_BOOTSTRAP_SCRIPT:
                raise UserNotificationException(f"Failed to find bootstrap script '{config.bootstrap_script}'. Make sure that the project is initialized correctly.")
            else:  # Fallback to default bootstrap script
                bootstrap_script = self.project_root_dir / DEFAULT_BOOTSTRAP_SCRIPT
                if not bootstrap_script.exists():
                    raise UserNotificationException("Failed to find bootstrap script. Make sure that the project is initialized correctly.")
        self.execution_context.create_process_executor(
            ["python3", bootstrap_script.as_posix()],
            cwd=self.project_root_dir,
        ).execute()
        self.execution_context.add_install_dirs(self.install_dirs)
        return 0

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        pass

    def get_needs_dependency_management(self) -> bool:
        return False
