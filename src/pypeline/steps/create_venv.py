from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from mashumaro import DataClassDictMixin
from py_app_dev.core.logging import logger

from pypeline.bootstrap.run import get_bootstrap_script

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


@dataclass
class CreateVEnvConfig(DataClassDictMixin):
    bootstrap_script: str = "bootstrap.py"
    python_executable: str = "python3"
    package_manager: Optional[str] = None


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
        bootstrap_args = []
        if not bootstrap_script.exists():
            self.logger.warning(f"Bootstrap script {bootstrap_script} does not exist. Use pypeline internal `bootstrap.py`.")
            bootstrap_script = get_bootstrap_script()
            # Only the internal bootstrap.py script supports arguments.
            bootstrap_args = ["--project-dir", self.project_root_dir.as_posix()]
            if config.package_manager:
                bootstrap_args.extend(["--package-manager", f'"{config.package_manager}"'])
        self.execution_context.create_process_executor(
            [config.python_executable, bootstrap_script.as_posix(), *bootstrap_args],
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
