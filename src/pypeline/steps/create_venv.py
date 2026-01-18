import io
import json
import re
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, fields
from enum import Enum, auto
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from mashumaro.config import TO_DICT_ADD_OMIT_NONE_FLAG, BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger

from pypeline.bootstrap.run import get_bootstrap_script
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


@dataclass
class CreateVEnvConfig(DataClassJSONMixin):
    bootstrap_script: Optional[str] = None
    python_executable: Optional[str] = None
    python_version: Optional[str] = None
    # deprecated: kept for backward compatibility
    package_manager: Optional[str] = None
    python_package_manager: Optional[str] = None
    python_package_manager_args: Optional[List[str]] = None
    bootstrap_packages: Optional[List[str]] = None
    bootstrap_cache_dir: Optional[str] = None
    venv_install_command: Optional[str] = None

    class Config(BaseConfig):
        """Base configuration for JSON serialization with omitted None values."""

        code_generation_options: ClassVar[List[str]] = [TO_DICT_ADD_OMIT_NONE_FLAG]

    def __post_init__(self) -> None:
        """
        Migrate deprecated package_manager field to python_package_manager.

        Ensures backward compatibility while preventing conflicting configurations.
        """
        # If both are set, they must match
        if self.package_manager is not None and self.python_package_manager is not None:
            if self.package_manager != self.python_package_manager:
                raise UserNotificationException(
                    f"Conflicting package manager configuration: "
                    f"package_manager='{self.package_manager}' vs python_package_manager='{self.python_package_manager}'. "
                    f"Please use only 'python_package_manager' (package_manager is deprecated)."
                )

        # Migrate from deprecated package_manager to python_package_manager
        if self.package_manager is not None and self.python_package_manager is None:
            self.python_package_manager = self.package_manager

        # Clear the deprecated field after migration
        self.package_manager = None

    @classmethod
    def from_json_file(cls, file_path: Path) -> "CreateVEnvConfig":
        try:
            result = cls.from_dict(json.loads(file_path.read_text()))
        except Exception as e:
            output = io.StringIO()
            traceback.print_exc(file=output)
            raise UserNotificationException(output.getvalue()) from e
        return result

    def to_json_string(self) -> str:
        return json.dumps(self.to_dict(omit_none=True), indent=2)

    def to_json_file(self, file_path: Path) -> None:
        file_path.write_text(self.to_json_string())

    def get_all_properties_names(self, excluded_names: Optional[List[str]] = None) -> List[str]:
        if excluded_names is None:
            excluded_names = []
        return [field.name for field in fields(self) if field.name not in excluded_names]

    def is_any_property_set(self, excluded_fields: Optional[List[str]] = None) -> bool:
        return any(getattr(self, field) is not None for field in self.get_all_properties_names(excluded_fields))


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
        self.package_manager = self.user_config.python_package_manager if self.user_config.python_package_manager else self.DEFAULT_PACKAGE_MANAGER
        self.venv_dir = self.project_root_dir / ".venv"

    def has_bootstrap_config(self) -> bool:
        """Check if user provided any bootstrap-specific configuration."""
        return self.user_config.is_any_property_set(["bootstrap_script", "python_executable"])

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
        bootstrap_config = CreateVEnvConfig()
        is_managed = False
        # Determine target script and mode
        if self.user_config.bootstrap_script:
            target_script = self.project_root_dir / self.user_config.bootstrap_script
            # If script exists, it's a "Custom Mode" execution (legacy behavior: run as-is)
            # If it misses, we enter "Managed Mode" to auto-create and run it
            is_managed = not target_script.exists()
            if is_managed:
                self.logger.warning(f"Bootstrap script {target_script} does not exist. Creating it from internal default.")
                # If there is a custom bootstrap config (bootstrap.json) in the project root,
                # we need to provide the internal script
                default_bootstrap_config = self.project_root_dir / "bootstrap.json"
                if default_bootstrap_config.exists():
                    self.logger.warning(f"Found bootstrap config {default_bootstrap_config}. Reading it.")
                    bootstrap_config = CreateVEnvConfig.from_json_file(default_bootstrap_config)
        else:
            target_script = self.target_internal_bootstrap_script
            is_managed = True

        if not is_managed:
            # Custom Mode: Run existing user script directly without injection
            self.execution_context.create_process_executor(
                [self.python_executable, target_script.as_posix()],
                cwd=self.project_root_dir,
            ).execute()
        else:
            # Managed Mode: Internal logic (Config generation + Args + File creation)
            skip_venv_delete = False
            python_executable = Path(sys.executable).absolute()
            if python_executable.is_relative_to(self.project_root_dir):
                self.logger.info(f"Detected that the python executable '{python_executable}' is from the virtual environment. Will update dependencies but skip venv deletion.")
                skip_venv_delete = True

            # Create bootstrap.json with all configuration
            # Populate config dynamically from CreateVEnvConfig fields
            # excluding internal/local fields like bootstrap_script/python_executable
            for field_name in self.user_config.get_all_properties_names(["bootstrap_script", "python_executable"]):
                val = getattr(self.user_config, field_name)
                if val is not None:
                    setattr(bootstrap_config, field_name, val)

            # Priority: input python_version takes precedence over config python_version
            input_python_version = self.execution_context.get_input("python_version")
            if input_python_version:
                bootstrap_config.python_version = input_python_version

            # Write bootstrap.json if any configuration is provided
            if bootstrap_config.is_any_property_set():
                self.bootstrap_config_file.parent.mkdir(exist_ok=True)
                bootstrap_config.to_json_file(self.bootstrap_config_file)
                self.logger.info(f"Created bootstrap configuration at {self.bootstrap_config_file}")

            # Build bootstrap script arguments
            bootstrap_args = [
                "--project-dir",
                self.project_root_dir.as_posix(),
            ]

            # Always use --config if bootstrap.json exists
            # Note: We use the internal .bootstrap/bootstrap.json location for consistency
            if self.bootstrap_config_file.exists():
                bootstrap_args.extend(["--config", self.bootstrap_config_file.as_posix()])

            if skip_venv_delete:
                bootstrap_args.append("--skip-venv-delete")

            # Create/Update the target bootstrap script from internal template
            target_script.parent.mkdir(parents=True, exist_ok=True)

            # Check if we need to write/update the file
            # If it's a missing custom file, we definitely write.
            # If it's the internal file, we check content hash/diff.
            should_write = False
            if not target_script.exists():
                should_write = True
            elif target_script == self.target_internal_bootstrap_script:
                if target_script.read_text() != self.internal_bootstrap_script.read_text():
                    should_write = True

            if should_write:
                target_script.write_text(self.internal_bootstrap_script.read_text())
                if target_script == self.target_internal_bootstrap_script:
                    self.logger.warning(f"Updated bootstrap script at {target_script}")

            # Run the bootstrap script
            self.execution_context.create_process_executor(
                [self.python_executable, target_script.as_posix(), *bootstrap_args],
                cwd=self.project_root_dir,
            ).execute()

        return 0

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def get_config(self) -> Optional[dict[str, str]]:
        return None

    def update_execution_context(self) -> None:
        self.execution_context.add_install_dirs(self.install_dirs)

    def get_needs_dependency_management(self) -> bool:
        # Always return False - the bootstrap script handles dependency management internally
        # via its Executor framework which checks input/output hashes and configuration changes
        return False
