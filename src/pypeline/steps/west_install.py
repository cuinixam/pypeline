from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


class WestInstall(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.artifacts_locator = execution_context.create_artifacts_locator()

    def get_name(self) -> str:
        return self.__class__.__name__

    @property
    def west_manifest_file(self) -> Path:
        return self.project_root_dir.joinpath("west.yaml")

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")
        try:
            self.execution_context.create_process_executor(
                [
                    "west",
                    "init",
                    "-l",
                    "--mf",
                    self.west_manifest_file.as_posix(),
                    self.artifacts_locator.build_dir.joinpath("west").as_posix(),
                ],
                cwd=self.project_root_dir,
            ).execute()
            self.execution_context.create_process_executor(
                ["west", "update"],
                cwd=self.artifacts_locator.build_dir,
            ).execute()
        except Exception as e:
            raise UserNotificationException(f"Failed to initialize and update with west: {e}") from e

        return 0

    def get_inputs(self) -> List[Path]:
        return [self.west_manifest_file]

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
