import io
import json
import re
import shutil
import subprocess
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
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


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

    def _verify_python_version(self, executable: str, expected_version: str) -> bool:
        """
        Verify that a Python executable matches the expected version.

        Args:
        ----
            executable: Name or path of Python executable to check
            expected_version: Expected version string (e.g., "3.11" or "3.11.5")

        Returns:
        -------
            True if the executable's version matches expected_version (ignoring patch),
            False otherwise or if the executable cannot be queried.

        """
        try:
            # Run python --version to get the version string
            result = subprocess.run(
                [executable, "--version"],  # noqa: S603
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return False

            # Parse version from output (e.g., "Python 3.11.5")
            version_output = result.stdout.strip()
            match = re.match(r"Python\s+(\d+)\.(\d+)(?:\.\d+)?", version_output)
            if not match:
                self.logger.warning(f"Could not parse version from: {version_output}")
                return False

            actual_major = match.group(1)
            actual_minor = match.group(2)

            # Parse expected version
            expected_parts = expected_version.split(".")
            if len(expected_parts) == 0:
                return False

            expected_major = expected_parts[0]
            # If only major version specified, only compare major
            if len(expected_parts) == 1:
                return actual_major == expected_major

            # Compare major.minor
            expected_minor = expected_parts[1]
            return actual_major == expected_major and actual_minor == expected_minor

        except (FileNotFoundError, OSError) as e:
            self.logger.debug(f"Failed to verify Python version for {executable}: {e}")
            return False

    def _find_python_executable(self, python_version: str) -> Optional[str]:
        """
        Find Python executable based on version string.

        Supports version formats:
        - "3.11.5" or "3.11" -> tries python3.11, python311, then falls back to python
        - "3" -> tries python3, then falls back to python

        Always ignores patch version. Falls back to generic 'python' if version-specific
        executables are not found, but verifies the version matches.

        Returns the first executable found in PATH, or None if not found or version mismatch.
        """
        # Handle empty string
        if not python_version:
            return None

        # Parse version string and extract components
        version_parts = python_version.split(".")

        if len(version_parts) == 0:
            return None

        major = version_parts[0]

        # Determine candidates based on version format
        candidates = []

        if len(version_parts) >= 2:
            # Has minor version (e.g., "3.11" or "3.11.5") - ignore patch
            minor = version_parts[1]
            major_minor = f"{major}.{minor}"
            major_minor_no_dot = f"{major}{minor}"

            candidates = [
                f"python{major_minor}",  # python3.11 (Linux/Mac preference)
                f"python{major_minor_no_dot}",  # python311 (Windows preference)
            ]
        else:
            # Only major version (e.g., "3")
            candidates = [f"python{major}"]

        # Try to find each candidate in PATH
        for candidate in candidates:
            executable_path = shutil.which(candidate)
            if executable_path:
                self.logger.debug(f"Found Python executable: {executable_path} (candidate: {candidate})")
                return candidate

        # Fallback to generic 'python' executable with version verification
        self.logger.debug(f"No version-specific Python executable found for {python_version}, trying generic 'python'")
        if shutil.which("python"):
            if self._verify_python_version("python", python_version):
                self.logger.info(f"Using generic 'python' executable (verified as Python {python_version})")
                return "python"
            else:
                self.logger.warning(f"Generic 'python' executable found but version does not match {python_version}")

        # No suitable executable found
        return None

    @property
    def python_executable(self) -> str:
        """
        Get python executable to use.

        Priority:
        1. Input from execution context (execution_context.get_input("python_version"))
        2. User-specified python_executable config
        3. Auto-detect from python_version config
        4. Current Python interpreter (sys.executable)
        """
        # Priority 1: Check execution context inputs first
        input_python_version = self.execution_context.get_input("python_version")
        if input_python_version:
            found_executable = self._find_python_executable(input_python_version)
            if found_executable:
                return found_executable
            # If version specified via input but not found, fail with helpful error
            raise UserNotificationException(
                f"Could not find Python {input_python_version} in PATH. Please install Python {input_python_version} or specify python_executable explicitly."
            )

        # Priority 2: User explicitly specified executable
        if self.user_config.python_executable:
            return self.user_config.python_executable

        # Priority 3: Auto-detect from python_version config
        if self.user_config.python_version:
            found_executable = self._find_python_executable(self.user_config.python_version)
            if found_executable:
                return found_executable
            # If version specified but not found, fail with helpful error
            raise UserNotificationException(
                f"Could not find Python {self.user_config.python_version} in PATH. Please install Python {self.user_config.python_version} or specify python_executable explicitly."
            )

        # Priority 4: Use current interpreter
        return sys.executable

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
        return self.project_root_dir / ".bootstrap/bootstrap.json"

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
            skip_venv_delete = False
            python_executable = Path(sys.executable).absolute()
            if python_executable.is_relative_to(self.project_root_dir):
                self.logger.info(f"Detected that the python executable '{python_executable}' is from the virtual environment. Will update dependencies but skip venv deletion.")
                skip_venv_delete = True

            # Create bootstrap.json with all configuration
            bootstrap_config = {}
            if self.user_config.package_manager:
                bootstrap_config["python_package_manager"] = self.user_config.package_manager

            # Priority: input python_version takes precedence over config python_version
            input_python_version = self.execution_context.get_input("python_version")
            if input_python_version:
                bootstrap_config["python_version"] = input_python_version
            elif self.user_config.python_version:
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
                self.bootstrap_config_file.parent.mkdir(exist_ok=True)
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

            if skip_venv_delete:
                bootstrap_args.append("--skip-venv-delete")

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
