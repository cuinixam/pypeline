import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from pypeline.bootstrap.run import get_bootstrap_script

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


@dataclass
class CreateVEnvConfig(DataClassDictMixin):
    bootstrap_script: Optional[str] = None
    python_executable: Optional[str] = None
    package_manager: Optional[str] = None


class BootstrapScriptType(Enum):
    CUSTOM = auto()
    INTERNAL = auto()


class CreateVEnv(PipelineStep[ExecutionContext]):
    DEFAULT_PACKAGE_MANAGER = "uv>=0.6"
    DEFAULT_PYTHON_EXECUTABLE = "python311"
    SUPPORTED_PACKAGE_MANAGERS: ClassVar[Dict[str, List[str]]] = {
        "uv": ["uv.lock", "pyproject.toml"],
        "pipenv": ["Pipfile", "Pipfile.lock"],
        "poetry": ["pyproject.toml", "poetry.lock"],
    }

    def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.user_config = CreateVEnvConfig.from_dict(config) if config else CreateVEnvConfig()
        self.bootstrap_script_type = BootstrapScriptType.CUSTOM if self.user_config.bootstrap_script else BootstrapScriptType.INTERNAL
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.bootstrap_script = get_bootstrap_script()
        self.package_manager = self.user_config.package_manager if self.user_config.package_manager else self.DEFAULT_PACKAGE_MANAGER
        self.python_executable = self.user_config.python_executable if self.user_config.python_executable else self.DEFAULT_PYTHON_EXECUTABLE
        self.venv_dir = self.project_root_dir / ".venv"

    @property
    def install_dirs(self) -> List[Path]:
        return [self.project_root_dir / dir for dir in [".venv/Scripts", ".venv/bin"] if (self.project_root_dir / dir).exists()]

    @property
    def package_manager_name(self) -> str:
        match = re.match(r"^([a-zA-Z0-9_-]+)", self.package_manager)
        if match:
            result = match.group(1)
            if result in self.SUPPORTED_PACKAGE_MANAGERS:
                return result
            else:
                raise UserNotificationException(f"Package manager {result} is not supported. Supported package managers are: {', '.join(self.SUPPORTED_PACKAGE_MANAGERS)}")
        else:
            raise UserNotificationException(f"Could not extract the package manager name from {self.package_manager}")

    def get_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")

        if self.user_config.bootstrap_script:
            bootstrap_script = self.project_root_dir / self.user_config.bootstrap_script
            if not bootstrap_script.exists():
                raise UserNotificationException(f"Bootstrap script {bootstrap_script} does not exist.")
            self.execution_context.create_process_executor(
                [self.python_executable, bootstrap_script.as_posix()],
                cwd=self.project_root_dir,
            ).execute()
        else:
            # The internal bootstrap script supports arguments.
            bootstrap_args = [
                "--project-dir",
                self.project_root_dir.as_posix(),
                "--package-manager",
                f'"{self.package_manager}"',
            ]
            self.execution_context.create_process_executor(
                [self.python_executable, self.bootstrap_script.as_posix(), *bootstrap_args],
                cwd=self.project_root_dir,
            ).execute()
        return 0

    def get_inputs(self) -> List[Path]:
        package_manager_relevant_file = self.SUPPORTED_PACKAGE_MANAGERS.get(self.package_manager_name, [])
        return [self.project_root_dir / file for file in package_manager_relevant_file] + [self.bootstrap_script]

    def get_outputs(self) -> List[Path]:
        return [self.venv_dir]

    def get_config(self) -> Optional[dict[str, str]]:
        return {
            "bootstrap_script": self.bootstrap_script.as_posix(),
            "python_executable": self.python_executable,
            "package_manager": self.package_manager,
        }

    def update_execution_context(self) -> None:
        self.execution_context.add_install_dirs(self.install_dirs)

    def get_needs_dependency_management(self) -> bool:
        return False if self.bootstrap_script_type == BootstrapScriptType.CUSTOM else True
