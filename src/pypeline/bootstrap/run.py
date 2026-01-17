import argparse
import configparser
import ensurepip
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess  # nosec
import sys
import venv
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import total_ordering
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")


DEFAULT_PACKAGE_MANAGER = "poetry>=2.1.0"
DEFAULT_BOOTSTRAP_PACKAGES = ["pip-system-certs>=4.0,<5.0"]
BOOTSTRAP_COMPLETE_MARKER = ".bootstrap-complete"
VENV_PYTHON_VERSION_MARKER = ".python_version"


def get_bootstrap_script() -> Path:
    """Get the path to the internal bootstrap script."""
    return Path(__file__)


@dataclass
class BootstrapConfig:
    """Configuration for the bootstrap process loaded from bootstrap.json."""

    python_version: str = ""
    package_manager: str = DEFAULT_PACKAGE_MANAGER
    package_manager_args: List[str] = field(default_factory=list)
    bootstrap_packages: List[str] = field(default_factory=lambda: list(DEFAULT_BOOTSTRAP_PACKAGES))
    bootstrap_cache_dir: Optional[Path] = None
    venv_install_command: Optional[str] = None

    @classmethod
    def from_json_file(cls, json_path: Path) -> "BootstrapConfig":
        """Load configuration from a JSON file."""
        if not json_path.exists():
            return cls()

        with json_path.open("r") as file_handle:
            data = json.load(file_handle)

        bootstrap_packages = data.get("bootstrap_packages", list(DEFAULT_BOOTSTRAP_PACKAGES))

        cache_dir_str = data.get("bootstrap_cache_dir")
        cache_dir = Path(cache_dir_str).expanduser() if cache_dir_str else None

        return cls(
            python_version=data.get("python_version", ""),
            package_manager=data.get("python_package_manager", DEFAULT_PACKAGE_MANAGER),
            package_manager_args=data.get("python_package_manager_args", []),
            bootstrap_packages=bootstrap_packages,
            bootstrap_cache_dir=cache_dir,
            venv_install_command=data.get("venv_install_command"),
        )

    def get_bootstrap_cache_dir(self) -> Path:
        """Return the bootstrap cache directory, defaulting to ~/.bootstrap."""
        if self.bootstrap_cache_dir:
            return self.bootstrap_cache_dir
        return Path.home() / ".bootstrap"

    def compute_bootstrap_env_hash(self) -> str:
        """Compute a hash for the bootstrap environment based on configuration."""
        if self.python_version:
            python_major_minor = ".".join(self.python_version.split(".")[:2])
        else:
            python_major_minor = f"{sys.version_info[0]}.{sys.version_info[1]}"
        components = [
            f"python={python_major_minor}",
            f"manager={self.package_manager}",
            f"packages={sorted(self.bootstrap_packages)}",
        ]
        content = "|".join(str(component) for component in components)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@total_ordering
class Version:
    def __init__(self, version_str: str) -> None:
        self.version = self.parse_version(version_str)

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        return tuple(map(int, re.split(r"\D+", version_str)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.version == other.version

    def __lt__(self, other: "Version") -> bool:
        return self.version < other.version

    def __repr__(self) -> str:
        return f"Version({'.'.join(map(str, self.version))})"


@dataclass
class PyPiSource:
    name: str
    url: str


@dataclass
class TomlSection:
    name: str
    content: str

    def __str__(self) -> str:
        return f"[{self.name}]\n{self.content}"


class PyPiSourceParser:
    @staticmethod
    def from_pyproject(project_dir: Path) -> Optional[PyPiSource]:
        pyproject_toml = project_dir / "pyproject.toml"
        pipfile = project_dir / "Pipfile"
        if pyproject_toml.exists():
            return PyPiSourceParser.from_toml_content(pyproject_toml.read_text(), "tool.poetry.source")
        elif pipfile.exists():
            return PyPiSourceParser.from_toml_content(pipfile.read_text(), "source")
        else:
            return None

    @staticmethod
    def from_toml_content(content: str, source_section_name: str) -> Optional[PyPiSource]:
        sections = PyPiSourceParser.get_toml_sections(content)
        for section in sections:
            if section.name == source_section_name:
                try:
                    parser = configparser.ConfigParser()
                    parser.read_string(str(section))
                    name = parser[section.name]["name"].strip('"')
                    url = parser[section.name]["url"].strip('"')
                    return PyPiSource(name, url)
                except KeyError:
                    raise UserNotificationException(
                        f"Could not parse PyPi source from section {section.name}. "
                        f"Please make sure the section has the following format:\n"
                        f"[{source_section_name}]\nname = 'name'\nurl = 'https://url'\nverify_ssl = true"
                    ) from None
        return None

    @staticmethod
    def get_toml_sections(toml_content: str) -> List[TomlSection]:
        # Use a regular expression to find all sections with [ or [[ at the beginning of the line
        raw_sections = re.findall(r"^\[+.*\]+\n(?:[^[]*\n)*", toml_content, re.MULTILINE)

        # Process each section
        sections = []
        for section in raw_sections:
            # Split the lines, from the first line extract the section name
            # and merge all the other lines into the content
            lines = section.splitlines()
            name_match = re.match(r"^\[+([^]]*)\]+", lines[0])
            if name_match:
                name = name_match.group(1).strip()
                content = "\n".join(lines[1:]).strip()
                sections.append(TomlSection(name, content))

        return sections


class Runnable(ABC):
    @abstractmethod
    def run(self) -> int:
        """Run stage."""

    @abstractmethod
    def get_name(self) -> str:
        """Get stage name."""

    @abstractmethod
    def get_inputs(self) -> List[Path]:
        """Get stage dependencies."""

    @abstractmethod
    def get_outputs(self) -> List[Path]:
        """Get stage outputs."""

    def get_config(self) -> Optional[dict[str, Any]]:
        """Get stage configuration for change detection."""
        return None


class RunInfoStatus(Enum):
    MATCH = (False, "Nothing has changed, previous execution information matches.")
    NO_INFO = (True, "No previous execution information found.")
    FILE_CHANGED = (True, "Dependencies have been changed.")
    CONFIG_CHANGED = (True, "Configuration has been changed.")

    def __init__(self, should_run: bool, message: str) -> None:
        self.should_run = should_run
        self.message = message


class Executor:
    """
    Accepts Runnable objects and executes them.

    It create a file with the same name as the runnable's name
    and stores the inputs and outputs with their hashes.
    If the file exists, it checks the hashes of the inputs and outputs
    and if they match, it skips the execution.
    """

    RUN_INFO_FILE_EXTENSION = ".deps.json"

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    @staticmethod
    def get_file_hash(path: Path) -> str:
        """
        Get the hash of a file.

        Returns an empty string if the file does not exist.
        """
        if path.is_file():
            with open(path, "rb") as file:
                bytes = file.read()
                readable_hash = hashlib.sha256(bytes).hexdigest()
                return readable_hash
        else:
            return ""

    def store_run_info(self, runnable: Runnable) -> None:
        file_info = {
            "inputs": {str(path): self.get_file_hash(path) for path in runnable.get_inputs()},
            "outputs": {str(path): self.get_file_hash(path) for path in runnable.get_outputs()},
            "config": runnable.get_config() or {},
        }

        run_info_path = self.get_runnable_run_info_file(runnable)
        run_info_path.parent.mkdir(parents=True, exist_ok=True)
        with run_info_path.open("w") as f:
            # pretty print the json file
            json.dump(file_info, f, indent=4)

    def get_runnable_run_info_file(self, runnable: Runnable) -> Path:
        return self.cache_dir / f"{runnable.get_name()}{self.RUN_INFO_FILE_EXTENSION}"

    def previous_run_info_matches(self, runnable: Runnable) -> RunInfoStatus:
        run_info_path = self.get_runnable_run_info_file(runnable)
        if not run_info_path.exists():
            return RunInfoStatus.NO_INFO

        with run_info_path.open() as f:
            previous_info = json.load(f)

        # Check if config has changed
        current_config = runnable.get_config() or {}
        previous_config = previous_info.get("config", {})
        if current_config != previous_config:
            return RunInfoStatus.CONFIG_CHANGED

        for file_type in ["inputs", "outputs"]:
            for path_str, previous_hash in previous_info[file_type].items():
                path = Path(path_str)
                if self.get_file_hash(path) != previous_hash:
                    return RunInfoStatus.FILE_CHANGED
        return RunInfoStatus.MATCH

    def execute(self, runnable: Runnable) -> int:
        run_info_status = self.previous_run_info_matches(runnable)
        if run_info_status.should_run:
            logger.info(f"Executing '{runnable.get_name()}': {run_info_status.message}")
            exit_code = runnable.run()
            self.store_run_info(runnable)
            return exit_code
        logger.info(f"Skipping '{runnable.get_name()}': {run_info_status.message}")

        return 0


class UserNotificationException(Exception):
    pass


class SubprocessExecutor:
    def __init__(
        self,
        command: Sequence[str | Path],
        cwd: Optional[Path] = None,
        capture_output: bool = True,
    ):
        self.command = " ".join([str(cmd) for cmd in command])
        self.current_working_directory = cwd
        self.capture_output = capture_output

    def execute(self) -> None:
        result = None
        try:
            current_dir = (self.current_working_directory or Path.cwd()).as_posix()
            logger.info(f"Running command: {self.command} in {current_dir}")
            # print all virtual environment variables
            logger.debug(json.dumps(dict(os.environ), indent=4))
            result = subprocess.run(
                self.command.split(),  # noqa: S603
                cwd=current_dir,
                capture_output=self.capture_output,
                text=True,  # to get stdout and stderr as strings instead of bytes
            )
            result.check_returncode()
        except subprocess.CalledProcessError as e:
            raise UserNotificationException(f"Command '{self.command}' failed with:\n{result.stdout if result else ''}\n{result.stderr if result else e}") from e


class VirtualEnvironment(ABC):
    def __init__(self, venv_dir: Path) -> None:
        self.venv_dir = venv_dir

    def create(self) -> None:
        """
        Create a new virtual environment.

        This should configure the virtual environment such that
        subsequent calls to `pip` and `run` operate within this environment.
        """
        try:
            venv.create(env_dir=self.venv_dir, with_pip=True)
            self.gitignore_configure()
        except PermissionError as e:
            if "python.exe" in str(e):
                raise UserNotificationException(
                    f"Failed to create virtual environment in {self.venv_dir}.\n"
                    f"Virtual environment python.exe is still running. "
                    f"Please kill all instances and run again.\nError: {e}"
                ) from e
            raise UserNotificationException(f"Failed to create virtual environment in {self.venv_dir}.\nPlease make sure you have the necessary permissions.\nError: {e}") from e

    def gitignore_configure(self) -> None:
        """Create a .gitignore file in the virtual environment directory to ignore all files."""
        gitignore_path = self.venv_dir / ".gitignore"
        with open(gitignore_path, "w") as gitignore_file:
            gitignore_file.write("*\n")

    def pip_configure(self, index_url: str, verify_ssl: bool = True) -> None:
        """
        Configure pip to use the given index URL and SSL verification setting.

        This method should behave as if the user had activated the virtual environment and run
        `pip config set global.index-url <index_url>` and
        `pip config set global.cert <verify_ssl>` from the command line.

        Args:
        ----
            index_url: The index URL to use for pip.
            verify_ssl: Whether to verify SSL certificates when using pip.

        """
        pip_ini_path = self.pip_config_path()
        with open(pip_ini_path, "w") as pip_ini_file:
            pip_ini_file.write(f"[global]\nindex-url = {index_url}\n")
            if not verify_ssl:
                pip_ini_file.write("cert = false\n")

    def pip(self, args: List[str]) -> None:
        SubprocessExecutor([self.pip_path().as_posix(), *args]).execute()

    @abstractmethod
    def python_path(self) -> Path:
        """Get the path to the Python executable within the virtual environment."""

    @abstractmethod
    def pip_path(self) -> Path:
        """Get the path to the pip executable within the virtual environment."""

    @abstractmethod
    def pip_config_path(self) -> Path:
        """Get the path to the pip configuration file within the virtual environment."""

    @abstractmethod
    def scripts_path(self) -> Path:
        """Get the path to the Scripts (Windows) or bin (Unix) directory within the virtual environment."""

    def run(self, args: List[str], capture_output: bool = True, cwd: Optional[Path] = None) -> None:
        """
        Run an arbitrary command within the virtual environment using the venv's Python.

        If the first argument is 'python', it will be replaced with the full path
        to the virtual environment's Python executable.

        Args:
        ----
            args: Command-line arguments. For example, `run(['python', '-m', 'poetry', 'install'])`
            capture_output: Whether to capture stdout/stderr.
            cwd: Working directory for the command.

        """
        command = list(args)
        if command and command[0] == "python":
            command[0] = self.python_path().as_posix()
        SubprocessExecutor(command, cwd=cwd, capture_output=capture_output).execute()


class WindowsVirtualEnvironment(VirtualEnvironment):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(venv_dir)

    def python_path(self) -> Path:
        return self.scripts_path().joinpath("python.exe")

    def pip_path(self) -> Path:
        return self.scripts_path().joinpath("pip.exe")

    def pip_config_path(self) -> Path:
        return self.venv_dir.joinpath("pip.ini")

    def scripts_path(self) -> Path:
        return self.venv_dir.joinpath("Scripts")


class UnixVirtualEnvironment(VirtualEnvironment):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(venv_dir)

    def python_path(self) -> Path:
        return self.scripts_path().joinpath("python")

    def pip_path(self) -> Path:
        return self.scripts_path().joinpath("pip")

    def pip_config_path(self) -> Path:
        return self.venv_dir.joinpath("pip.conf")

    def scripts_path(self) -> Path:
        return self.venv_dir.joinpath("bin")


def instantiate_os_specific_venv(venv_dir: Path) -> VirtualEnvironment:
    """Create an OS-specific VirtualEnvironment instance."""
    if sys.platform.startswith("win32"):
        return WindowsVirtualEnvironment(venv_dir)
    elif sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
        return UnixVirtualEnvironment(venv_dir)
    else:
        raise UserNotificationException(f"Unsupported operating system: {sys.platform}")


def extract_package_manager_name(package_manager_spec: str) -> str:
    """Extract the package manager name from a specification like 'poetry>=1.7.1'."""
    match = re.match(r"^([a-zA-Z0-9_-]+)", package_manager_spec)
    if match:
        return match.group(1)
    raise UserNotificationException(f"Could not extract the package manager name from {package_manager_spec}")


class CreateBootstrapEnvironment(Runnable):
    """
    Creates a shared bootstrap environment with the package manager installed.

    The bootstrap environment is stored in a user-level cache directory
    (default: ~/.bootstrap/<hash>/) and is shared across projects with
    the same configuration.
    """

    def __init__(self, config: BootstrapConfig, project_dir: Path) -> None:
        self.config = config
        self.project_dir = project_dir
        self.env_hash = config.compute_bootstrap_env_hash()
        self.bootstrap_env_dir = config.get_bootstrap_cache_dir() / self.env_hash
        self.venv_dir = self.bootstrap_env_dir / ".venv"
        self.virtual_env = instantiate_os_specific_venv(self.venv_dir)
        self.marker_file = self.bootstrap_env_dir / BOOTSTRAP_COMPLETE_MARKER

    def run(self) -> int:
        self._create_environment_atomic()
        return 0

    def _is_valid_environment(self) -> bool:
        """Check if the bootstrap environment exists and is valid."""
        if not self.marker_file.exists():
            return False

        try:
            stored_hash = self.marker_file.read_text().strip()
            if stored_hash != self.env_hash:
                logger.info(f"Bootstrap environment hash mismatch: {stored_hash} != {self.env_hash}")
                return False
        except OSError:
            return False

        if not self.virtual_env.pip_path().exists():
            logger.info("Bootstrap environment pip not found, will recreate.")
            return False

        return True

    def _create_environment_atomic(self) -> None:
        """Create the bootstrap environment, replacing any existing invalid environment."""
        try:
            # Remove existing directory if present (invalid or leftover from failed attempt)
            if self.bootstrap_env_dir.exists():
                logger.info(f"Removing existing bootstrap environment at {self.bootstrap_env_dir}")
                shutil.rmtree(self.bootstrap_env_dir)

            # Create bootstrap environment directory
            self.bootstrap_env_dir.mkdir(parents=True, exist_ok=True)
            bootstrap_venv = instantiate_os_specific_venv(self.venv_dir)

            logger.info(f"Creating bootstrap environment in {self.bootstrap_env_dir}")
            venv.create(env_dir=self.venv_dir, with_pip=True)

            # Configure pip with PyPI source if available
            pypi_source = PyPiSourceParser.from_pyproject(self.project_dir)
            if pypi_source:
                bootstrap_venv.pip_configure(index_url=pypi_source.url, verify_ssl=True)

            # Build pip install arguments
            packages_to_install = [self.config.package_manager, *self.config.bootstrap_packages]
            pip_args = ["install", *packages_to_install]

            # Handle SSL certificates for older pip versions
            if Version(ensurepip.version()) < Version("24.2"):
                if pypi_source and (hostname := urlparse(pypi_source.url).hostname):
                    pip_args.extend(["--trusted-host", hostname])
                else:
                    pip_args.extend(
                        [
                            "--trusted-host",
                            "pypi.org",
                            "--trusted-host",
                            "pypi.python.org",
                            "--trusted-host",
                            "files.pythonhosted.org",
                        ]
                    )

            logger.info(f"Installing bootstrap packages: {packages_to_install}")
            bootstrap_venv.pip(pip_args)

            # Write the completion marker
            marker_path = self.bootstrap_env_dir / BOOTSTRAP_COMPLETE_MARKER
            marker_path.write_text(self.env_hash)

            # Update the virtual_env reference
            self.virtual_env = instantiate_os_specific_venv(self.venv_dir)

            logger.info(f"Bootstrap environment created successfully at {self.bootstrap_env_dir}")

        except Exception as exc:
            logger.error(f"Bootstrap environment creation failed at {self.bootstrap_env_dir}")
            raise UserNotificationException(f"Failed to create bootstrap environment: {exc}") from exc

    def get_name(self) -> str:
        return "create-bootstrap-environment"

    def get_inputs(self) -> List[Path]:
        # No file-based inputs for shared bootstrap environment
        return []

    def get_outputs(self) -> List[Path]:
        return [self.marker_file]

    def get_config(self) -> Optional[dict[str, Any]]:
        """Return configuration that affects the bootstrap environment."""
        return {
            "package_manager": self.config.package_manager,
            "bootstrap_packages": sorted(self.config.bootstrap_packages),
            "python_version": self.config.python_version,
        }


class CreateVirtualEnvironment(Runnable):
    """Creates the project virtual environment using the bootstrap environment's package manager."""

    def __init__(
        self,
        root_dir: Path,
        bootstrap_env: CreateBootstrapEnvironment,
        skip_venv_delete: bool = False,
    ) -> None:
        self.root_dir = root_dir
        self.venv_dir = self.root_dir / ".venv"
        self.bootstrap_dir = self.root_dir / ".bootstrap"
        self.virtual_env = instantiate_os_specific_venv(self.venv_dir)
        self.bootstrap_env = bootstrap_env
        self.config = bootstrap_env.config
        self.python_version_marker = self.venv_dir / VENV_PYTHON_VERSION_MARKER
        self.skip_venv_delete = skip_venv_delete

    @property
    def package_manager_name(self) -> str:
        return extract_package_manager_name(self.config.package_manager)

    def _check_python_version_compatibility(self) -> None:
        """
        Check if the existing venv was created with the same Python version.

        If the Python version has changed (e.g., switching branches), delete the
        existing venv so it can be recreated by the package manager.
        If skip_venv_delete is True, log a warning instead of deleting.
        """
        if not self.venv_dir.exists():
            return

        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        if not self.python_version_marker.exists():
            if self.skip_venv_delete:
                logger.warning(f"No Python version marker found in {self.venv_dir}. Cannot verify venv compatibility, but skipping deletion as requested.")
            else:
                logger.info(
                    f"No Python version marker found in {self.venv_dir}. "
                    f"This venv may have been created before version tracking was added. "
                    f"Deleting {self.venv_dir} to ensure clean state."
                )
                shutil.rmtree(self.venv_dir)
            return

        try:
            stored_version = self.python_version_marker.read_text().strip()
            if stored_version != current_version:
                if self.skip_venv_delete:
                    logger.warning(
                        f"Python version changed from {stored_version} to {current_version}. Skipping venv deletion as requested - dependencies will be updated in place."
                    )
                else:
                    logger.info(f"Python version changed from {stored_version} to {current_version}. Deleting {self.venv_dir} for recreation.")
                    shutil.rmtree(self.venv_dir)
        except OSError as exc:
            logger.warning(f"Could not read Python version marker: {exc}")

    def _write_python_version_marker(self, version: str) -> None:
        """Write the Python version marker to track the venv's Python version."""
        try:
            self.python_version_marker.write_text(version)
        except OSError as exc:
            logger.warning(f"Could not write Python version marker: {exc}")

    def _set_env_var(self, key: str, value: str) -> None:
        """Helper method to set environment variables (easier to mock in tests)."""
        os.environ[key] = value

    def _ensure_in_project_venv(self) -> None:
        """Configure package managers to create venv in-project (.venv in repository)."""
        if self.package_manager_name == "poetry":
            # Set environment variable for poetry to create venv in-project
            self._set_env_var("POETRY_VIRTUALENVS_IN_PROJECT", "true")
        elif self.package_manager_name == "pipenv":
            # Set environment variable for pipenv
            self._set_env_var("PIPENV_VENV_IN_PROJECT", "1")
        # UV creates .venv in-project by default, no configuration needed

    def _ensure_correct_python_version(self) -> None:
        """Ensure the correct Python version is used in the virtual environment."""
        if self.package_manager_name == "poetry":
            # Make Poetry use the Python interpreter it's being run with
            self._set_env_var("POETRY_VIRTUALENVS_PREFER_ACTIVE_PYTHON", "false")
            self._set_env_var("POETRY_VIRTUALENVS_USE_POETRY_PYTHON", "true")
        elif self.package_manager_name == "uv":
            # Make UV use the Python interpreter it's being run with
            self._set_env_var("UV_PYTHON", self.config.python_version)
            self._set_env_var("UV_MANAGED_PYTHON", "false")
            self._set_env_var("UV_NO_PYTHON_DOWNLOADS", "true")

    def _get_install_argument(self) -> str:
        if self.package_manager_name == "uv":
            return "sync"
        return "install"

    def _get_install_command(self) -> List[str]:
        if self.config.venv_install_command:
            return self.config.venv_install_command.split()

        return [
            str(self.bootstrap_env.virtual_env.scripts_path() / self.package_manager_name),
            self._get_install_argument(),
            *self.config.package_manager_args,
        ]

    def run(self) -> int:
        self._check_python_version_compatibility()
        self._ensure_in_project_venv()
        self._ensure_correct_python_version()

        # Get the PyPi source from pyproject.toml or Pipfile if it is defined
        pypi_source = PyPiSourceParser.from_pyproject(self.root_dir)

        # Use the bootstrap environment's package manager to install dependencies
        # The package manager will create the .venv if it doesn't exist
        logger.info(f"Using bootstrap environment at {self.bootstrap_env.venv_dir}")
        self.bootstrap_env.virtual_env.run(self._get_install_command(), capture_output=True, cwd=self.root_dir)

        # Write Python version marker after package manager creates/updates venv
        if self.venv_dir.exists():
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self._write_python_version_marker(current_version)

        # Configure pip if needed (after venv is created by package manager)
        if pypi_source and self.venv_dir.exists():
            self.virtual_env.pip_configure(index_url=pypi_source.url, verify_ssl=True)

        return 0

    def get_name(self) -> str:
        return "create-virtual-environment"

    def get_inputs(self) -> List[Path]:
        """Get input dependencies based on package manager and actual bootstrap configuration."""
        inputs = []

        # Add package manager specific lock/config files
        package_manager_files = {
            "uv": ["uv.lock", "pyproject.toml"],
            "poetry": ["poetry.lock", "poetry.toml", "pyproject.toml"],
            "pipenv": ["Pipfile", "Pipfile.lock", ".env"],
        }

        if self.package_manager_name in package_manager_files:
            for file in package_manager_files[self.package_manager_name]:
                inputs.append(self.root_dir / file)

        # Add bootstrap script (always tracked since CreateVEnv creates it)
        inputs.append(self.bootstrap_dir / "bootstrap.py")

        # Add the bootstrap environment marker
        inputs.append(self.bootstrap_env.marker_file)

        return inputs

    def get_outputs(self) -> List[Path]:
        """
        Return the Scripts/bin directories for both bootstrap and project environments.

        These paths are recorded in the .deps.json file, allowing other tools to discover
        the package manager location (bootstrap env) and project tools (project env).
        """
        return [
            self.virtual_env.scripts_path(),
            self.bootstrap_env.virtual_env.scripts_path(),
        ]

    def get_config(self) -> Optional[dict[str, Any]]:
        """Return configuration that affects the project environment."""
        return {
            "package_manager": self.config.package_manager,
            "package_manager_args": self.config.package_manager_args,
            "venv_install_command": self.config.venv_install_command,
            "python_version": self.config.python_version,
        }


def print_environment_info() -> None:
    str_bar = "".join(["-" for _ in range(80)])
    logger.debug(str_bar)
    logger.debug("Environment: \n" + json.dumps(dict(os.environ), indent=4))
    logger.info(str_bar)
    logger.info(f"Arguments: {sys.argv[1:]}")
    logger.info(str_bar)


def main() -> int:
    try:
        parser = argparse.ArgumentParser(description="Create the python virtual environment.")
        parser.add_argument(
            "--package-manager",
            type=str,
            required=False,
            default="poetry>=2.0",
            help="Specify the package manager to use (e.g., poetry>=2.0).",
        )
        parser.add_argument(
            "--project-dir",
            type=Path,
            required=False,
            default=Path.cwd(),
            help="Specify the project directory (default: current working directory).",
        )
        parser.add_argument(
            "--skip-venv-delete",
            action="store_true",
            required=False,
            default=False,
            help="Skip deleting the virtual environment (used when running from within the venv). Dependencies will still be updated.",
        )
        parser.add_argument(
            "--config",
            type=Path,
            required=False,
            help="Path to bootstrap.json configuration file.",
        )
        args = parser.parse_args()

        project_dir = args.project_dir

        # Load configuration from bootstrap.json if provided, otherwise use CLI args
        if args.config:
            config_path = args.config if args.config.is_absolute() else project_dir / args.config
            config = BootstrapConfig.from_json_file(config_path)
        else:
            # Use CLI arguments for backward compatibility
            config = BootstrapConfig(
                package_manager=args.package_manager,
            )

        # Step 1: Create the bootstrap environment (shared cache)
        bootstrap_env = CreateBootstrapEnvironment(config, project_dir)
        bootstrap_executor = Executor(bootstrap_env.bootstrap_env_dir)
        bootstrap_executor.execute(bootstrap_env)

        # Step 2: Create the project virtual environment using the bootstrap env
        # When skip_venv_delete is True (e.g., running from within the venv),
        # we still update dependencies but skip deleting the venv to avoid write access exceptions
        project_venv = CreateVirtualEnvironment(project_dir, bootstrap_env, skip_venv_delete=args.skip_venv_delete)
        project_executor = Executor(project_venv.venv_dir)
        project_executor.execute(project_venv)

    except UserNotificationException as exc:
        logger.error(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
