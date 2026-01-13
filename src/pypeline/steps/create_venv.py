import io
import json
import re
import sys
import traceback
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from mashumaro import DataClassDictMixin
from mashumaro.mixins.json import DataClassJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from pypeline import __version__
from pypeline.bootstrap.run import get_bootstrap_script

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


@dataclass
class CreateVEnvConfig(DataClassDictMixin):
    bootstrap_script: Optional[str] = None
    python_executable: Optional[str] = None
    # Bootstrap-specific configuration
    package_manager: Optional[str] = None
    python_version: Optional[str] = None
    package_manager_args: Optional[List[str]] = None
    bootstrap_packages: Optional[List[str]] = None
    bootstrap_cache_dir: Optional[str] = None
    venv_install_command: Optional[str] = None


class BootstrapScriptType(Enum):
    CUSTOM = auto()
    INTERNAL = auto()


@dataclass
class CreateVEnvDeps(DataClassJSONMixin):
    outputs: List[Path]

    @classmethod
    def from_json_file(cls, file_path: Path) -> "CreateVEnvDeps":
        try:
            result = cls.from_dict(json.loads(file_path.read_text()))
        except Exception as e:
            output = io.StringIO()
            traceback.print_exc(file=output)
            raise UserNotificationException(output.getvalue()) from e
        return result


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
        self.internal_bootstrap_script = get_bootstrap_script()
        self.package_manager = self.user_config.package_manager if self.user_config.package_manager else self.DEFAULT_PACKAGE_MANAGER
        self.python_executable = self.user_config.python_executable if self.user_config.python_executable else self.DEFAULT_PYTHON_EXECUTABLE
        self.venv_dir = self.project_root_dir / ".venv"

    @property
    def has_bootstrap_config(self) -> bool:
        """Check if user provided any bootstrap-specific configuration."""
        return any(
            [
                self.user_config.package_manager,
                self.user_config.python_version,
                self.user_config.package_manager_args,
                self.user_config.bootstrap_packages,
                self.user_config.bootstrap_cache_dir,
                self.user_config.venv_install_command,
            ]
        )

    @property
    def install_dirs(self) -> List[Path]:
        deps_file = self.project_root_dir / ".venv" / "create-virtual-environment.deps.json"
        if deps_file.exists():
            deps = CreateVEnvDeps.from_json_file(deps_file)
            if deps.outputs:
                return deps.outputs
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

    @property
    def target_internal_bootstrap_script(self) -> Path:
        return self.project_root_dir.joinpath(".bootstrap/bootstrap.py")

    @property
    def bootstrap_config_file(self) -> Path:
        return self.project_root_dir / "bootstrap.json"

    def get_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")

        if self.user_config.bootstrap_script:
            # User provided a custom bootstrap script - run it directly
            bootstrap_script = self.project_root_dir / self.user_config.bootstrap_script
            if not bootstrap_script.exists():
                raise UserNotificationException(f"Bootstrap script {bootstrap_script} does not exist.")
            self.execution_context.create_process_executor(
                [self.python_executable, bootstrap_script.as_posix()],
                cwd=self.project_root_dir,
            ).execute()
        else:
            # Use internal bootstrap script
            skip_venv_creation = False
            python_executable = Path(sys.executable).absolute()
            if python_executable.is_relative_to(self.project_root_dir):
                self.logger.info(f"Detected that the python executable '{python_executable}' is from the virtual environment. Skip updating the virtual environment.")
                skip_venv_creation = True

            # Create bootstrap.json with all configuration
            bootstrap_config = {}
            if self.user_config.package_manager:
                bootstrap_config["python_package_manager"] = self.user_config.package_manager
            if self.user_config.python_version:
                bootstrap_config["python_version"] = self.user_config.python_version
            if self.user_config.package_manager_args:
                bootstrap_config["python_package_manager_args"] = self.user_config.package_manager_args
            if self.user_config.bootstrap_packages:
                bootstrap_config["bootstrap_packages"] = self.user_config.bootstrap_packages
            if self.user_config.bootstrap_cache_dir:
                bootstrap_config["bootstrap_cache_dir"] = self.user_config.bootstrap_cache_dir
            if self.user_config.venv_install_command:
                bootstrap_config["venv_install_command"] = self.user_config.venv_install_command

            # Write bootstrap.json if any configuration is provided
            if bootstrap_config:
                self.bootstrap_config_file.write_text(json.dumps(bootstrap_config, indent=2))
                self.logger.info(f"Created bootstrap configuration at {self.bootstrap_config_file}")

            # Build bootstrap script arguments
            bootstrap_args = [
                "--project-dir",
                self.project_root_dir.as_posix(),
            ]

            # Always use --config if bootstrap.json exists
            if self.bootstrap_config_file.exists():
                bootstrap_args.extend(["--config", self.bootstrap_config_file.as_posix()])

            if skip_venv_creation:
                bootstrap_args.append("--skip-venv-creation")

            # Copy the internal bootstrap script to the project root .bootstrap/bootstrap.py
            self.target_internal_bootstrap_script.parent.mkdir(exist_ok=True)
            if not self.target_internal_bootstrap_script.exists() or self.target_internal_bootstrap_script.read_text() != self.internal_bootstrap_script.read_text():
                self.target_internal_bootstrap_script.write_text(self.internal_bootstrap_script.read_text())
                self.logger.warning(f"Updated bootstrap script at {self.target_internal_bootstrap_script}")

            # Run the copied bootstrap script
            self.execution_context.create_process_executor(
                [self.python_executable, self.target_internal_bootstrap_script.as_posix(), *bootstrap_args],
                cwd=self.project_root_dir,
            ).execute()

        return 0

    def get_inputs(self) -> List[Path]:
        package_manager_relevant_file = self.SUPPORTED_PACKAGE_MANAGERS.get(self.package_manager_name, [])
        inputs = [self.project_root_dir / file for file in package_manager_relevant_file]
        # Include bootstrap.json if it exists
        if self.bootstrap_config_file.exists():
            inputs.append(self.bootstrap_config_file)
        return inputs

    def get_outputs(self) -> List[Path]:
        outputs = [self.venv_dir]
        if self.bootstrap_script_type == BootstrapScriptType.INTERNAL:
            outputs.append(self.target_internal_bootstrap_script)
            # Include bootstrap.json if it will be created
            if self.has_bootstrap_config:
                outputs.append(self.bootstrap_config_file)
        return outputs

    def get_config(self) -> Optional[dict[str, str]]:
        return {
            "version": __version__,
            "python_executable": self.python_executable,
            "package_manager": self.package_manager,
        }

    def update_execution_context(self) -> None:
        self.execution_context.add_install_dirs(self.install_dirs)

    def get_needs_dependency_management(self) -> bool:
        # Always return False - the bootstrap script handles dependency management internally
        # via its Executor framework which checks input/output hashes and configuration changes
        return False
