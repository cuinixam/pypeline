import argparse
import configparser
import ensurepip
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import venv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")


def get_bootstrap_script() -> Path:
    """Get the path to the internal bootstrap script."""
    return Path(__file__)


@total_ordering
class Version:
    def __init__(self, version_str: str) -> None:
        self.version = self.parse_version(version_str)

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        """Convert a version string into a tuple of integers for comparison."""
        return tuple(map(int, re.split(r"\D+", version_str)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.version == other.version

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
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
    def find_pypi_source_in_content(content: str) -> Optional[PyPiSource]:
        """Parses TOML content, finds the first section containing 'name' and 'url' keys, and returns it as a PyPiSource."""
        sections = PyPiSourceParser.get_toml_sections(content)
        logger.debug(f"Found {len(sections)} potential sections in TOML content.")

        for section in sections:
            logger.debug(f"Checking section: [{section.name}]")
            try:
                parser = configparser.ConfigParser(interpolation=None)  # Disable interpolation
                # Provide the section string directly to read_string
                # The TomlSection.__str__ method formats it correctly
                parser.read_string(str(section))

                # Check if the section was parsed and contains the required keys
                if section.name in parser and "name" in parser[section.name] and "url" in parser[section.name]:
                    name = parser[section.name]["name"].strip("\"' ")  # Strip quotes and whitespace
                    url = parser[section.name]["url"].strip("\"' ")  # Strip quotes and whitespace

                    # Ensure values are not empty after stripping
                    if name and url:
                        logger.info(f"Found valid PyPI source in section '[{section.name}]': name='{name}', url='{url}'")
                        return PyPiSource(name=name, url=url)
                    else:
                        logger.debug(f"Section '[{section.name}]' contains 'name' and 'url' keys, but one or both values are empty.")
                else:
                    logger.debug(f"Section '[{section.name}]' does not contain both 'name' and 'url' keys.")

            except configparser.Error as e:
                # This might happen if the section content is not valid INI/config format
                # or if the section name itself causes issues (though get_toml_sections should handle it)
                logger.debug(f"Could not parse section '[{section.name}]' with configparser: {e}")
                # Continue to the next section
                continue

        logger.info("No suitable PyPI source section found in the provided TOML content.")
        return None

    @staticmethod
    def from_pyproject(project_dir: Path) -> Optional[PyPiSource]:
        """Reads pyproject.toml or Pipfile and finds the PyPI source configuration without relying on a specific section name."""
        pyproject_toml = project_dir / "pyproject.toml"
        pipfile = project_dir / "Pipfile"
        content = None
        file_checked = None

        if pyproject_toml.exists():
            logger.debug(f"Checking for PyPI source in {pyproject_toml}")
            content = pyproject_toml.read_text()
            file_checked = pyproject_toml
        elif pipfile.exists():
            logger.debug(f"Checking for PyPI source in {pipfile}")
            content = pipfile.read_text()
            file_checked = pipfile

        if content:
            source = PyPiSourceParser.find_pypi_source_in_content(content)
            if source:
                return source
            else:
                logger.debug(f"No PyPI source definition found in {file_checked}")
                return None
        else:
            logger.debug("Neither pyproject.toml nor Pipfile found in the project directory.")
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


class UserNotificationException(Exception):
    pass


class SubprocessExecutor:
    def __init__(
        self,
        command: List[str | Path],
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
            result = subprocess.run(self.command.split(), cwd=current_dir, capture_output=self.capture_output, text=True)  # noqa: S603
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
                    f"Failed to create virtual environment in {self.venv_dir}.\nVirtual environment python.exe is still running."
                    f" Please kill all instances and run again.\nError: {e}"
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

        This method should behave as if the user had activated the virtual environment
        and run `pip config set global.index-url <index_url>` and
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
    def pip_path(self) -> Path:
        """Get the path to the pip executable within the virtual environment."""

    @abstractmethod
    def pip_config_path(self) -> Path:
        """Get the path to the pip configuration file within the virtual environment."""

    @abstractmethod
    def run(self, args: List[str], capture_output: bool = True) -> None:
        """
        Run an arbitrary command within the virtual environment.

        This method should behave as if the user had activated the virtual environment
        and run the given command from the command line.

        """


class WindowsVirtualEnvironment(VirtualEnvironment):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(venv_dir)
        self.activate_script = self.venv_dir.joinpath("Scripts/activate")

    def pip_path(self) -> Path:
        return self.venv_dir.joinpath("Scripts/pip.exe")

    def pip_config_path(self) -> Path:
        return self.venv_dir.joinpath("pip.ini")

    def run(self, args: List[str], capture_output: bool = True) -> None:
        SubprocessExecutor(
            command=[f"cmd /c {self.activate_script.as_posix()} && ", *args],
            capture_output=capture_output,
        ).execute()


class UnixVirtualEnvironment(VirtualEnvironment):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(venv_dir)
        self.activate_script = self.venv_dir.joinpath("bin/activate")

    def pip_path(self) -> Path:
        return self.venv_dir.joinpath("bin/pip")

    def pip_config_path(self) -> Path:
        return self.venv_dir.joinpath("pip.conf")

    def run(self, args: List[str], capture_output: bool = True) -> None:
        # Create a temporary shell script
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write("#!/bin/bash\n")  # Add a shebang line
            f.write(f"source {self.activate_script.as_posix()}\n")  # Write the activate command
            f.write(" ".join(args))  # Write the provided command
            temp_script_path = f.name  # Get the path of the temporary script

        # Make the temporary script executable
        SubprocessExecutor(["chmod", "+x", temp_script_path]).execute()
        # Run the temporary script
        SubprocessExecutor(
            command=[f"{Path(temp_script_path).as_posix()}"],
            capture_output=capture_output,
        ).execute()
        # Delete the temporary script
        os.remove(temp_script_path)


class CreateVirtualEnvironment:
    def __init__(self, root_dir: Path, package_manager: str, skip_venv_creation: bool = False) -> None:
        self.root_dir = root_dir
        self.venv_dir = self.root_dir / ".venv"
        self.virtual_env = self.instantiate_os_specific_venv(self.venv_dir)
        self.package_manager = package_manager.replace('"', "").replace("'", "")
        self.execution_info_file = self.venv_dir / "virtual_env_exec_info.json"
        self.skip_venv_creation = skip_venv_creation

    @property
    def package_manager_name(self) -> str:
        match = re.match(r"^([a-zA-Z0-9_-]+)", self.package_manager)
        if match:
            return match.group(1)
        else:
            raise UserNotificationException(f"Could not extract the package manager name from {self.package_manager}")

    def get_install_argument(self) -> str:
        """Determine the install argument based on the package manager name."""
        if self.package_manager_name == "uv":
            return "sync"
        return "install"

    def run(self) -> int:
        if not self.skip_venv_creation:
            self.virtual_env.create()
        else:
            logger.info("Skipping virtual environment creation as requested.")

        # Get the PyPi source from pyproject.toml or Pipfile if it is defined
        pypi_source = PyPiSourceParser.from_pyproject(self.root_dir)
        if pypi_source:
            self.virtual_env.pip_configure(index_url=pypi_source.url, verify_ssl=True)
        # We need pip-system-certs in venv to use certificates, that are stored in the system's trust store,
        pip_args = ["install", self.package_manager, "pip-system-certs>=4.0,<5.0"]
        # but to install it, we need either a pip version with the trust store feature or to trust the host
        # (trust store feature enabled by default since 24.2)
        if Version(ensurepip.version()) < Version("24.2"):
            # Add trusted host of configured source for older Python versions
            if pypi_source and pypi_source.url:
                if hostname := urlparse(pypi_source.url).hostname:
                    pip_args.extend(["--trusted-host", hostname])
            else:
                pip_args.extend(["--trusted-host", "pypi.org", "--trusted-host", "pypi.python.org", "--trusted-host", "files.pythonhosted.org"])
        self.virtual_env.pip(pip_args)
        self.virtual_env.run(["python", "-m", self.package_manager_name, self.get_install_argument()])
        return 0

    @staticmethod
    def instantiate_os_specific_venv(venv_dir: Path) -> VirtualEnvironment:
        if sys.platform.startswith("win32"):
            return WindowsVirtualEnvironment(venv_dir)
        elif sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
            return UnixVirtualEnvironment(venv_dir)
        else:
            raise UserNotificationException(f"Unsupported operating system: {sys.platform}")


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
            "--skip-venv-creation",
            action="store_true",
            required=False,
            default=False,
            help="Skip the virtual environment creation process.",
        )
        args = parser.parse_args()

        CreateVirtualEnvironment(args.project_dir, package_manager=args.package_manager, skip_venv_creation=args.skip_venv_creation).run()
    except UserNotificationException as e:
        logger.error(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
