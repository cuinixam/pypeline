from pathlib import Path
from typing import List

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


class CreateVEnv(PipelineStep):
    def __init__(self, execution_context: ExecutionContext, output_dir: Path) -> None:
        super().__init__(execution_context, output_dir)
        self.logger = logger.bind()
        self.logger = logger.bind()

    @property
    def install_dirs(self) -> List[Path]:
        return [self.project_root_dir / dir for dir in [".venv/Scripts", ".venv/bin"] if (self.project_root_dir / dir).exists()]

    def get_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")
        build_script_path = self.project_root_dir / "bootstrap.py"
        if not build_script_path.exists():
            raise UserNotificationException("Failed to find bootstrap script. Make sure that the project is initialized correctly.")
        self.execution_context.create_process_executor(
            ["python", build_script_path.as_posix()],
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
