import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.env_setup_scripts import BatEnvSetupScriptGenerator, EnvSetupScriptGenerator, Ps1EnvSetupScriptGenerator
from py_app_dev.core.logging import logger

from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


def read_dot_env_file(dot_env_file: Path) -> Dict[str, str]:
    """Reads a .env file and returns a dictionary of environment variables."""
    env_vars = {}
    with dot_env_file.open("r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars


class ShEnvSetupScriptGenerator(EnvSetupScriptGenerator):
    """Generates a bash/sh script to set environment variables and update PATH."""

    def generate_content(self) -> str:
        lines = ["#!/bin/bash"]

        for key, value in self.environment.items():
            # Escape single quotes by replacing ' with '\''
            # This closes the string, adds an escaped quote, then reopens the string
            escaped_value = value.replace("'", "'\\''")
            # Use single quotes for the value to prevent variable expansion
            lines.append(f"export {key}='{escaped_value}'")

        if self.install_dirs:
            # Convert to POSIX paths to ensure forward slashes on all platforms
            path_string = ":".join([path.as_posix() for path in self.install_dirs])
            # Escape single quotes in paths
            escaped_path_string = path_string.replace("'", "'\\''")
            lines.append(f"export PATH='{escaped_path_string}':\"$PATH\"")
        else:
            self.logger.debug("No install directories provided for PATH update.")
        lines.append("")

        return "\n".join(lines)


class GenerateEnvSetupScript(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: Optional[str], config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self._generated_scripts: List[Path] = []

    def run(self) -> None:
        logger.info(f"Generating environment setup scripts under {self.output_dir} ...")

        # Read the .env file and set up the environment variables
        dot_env_file = self.execution_context.project_root_dir.joinpath(".env")
        if dot_env_file.exists():
            logger.debug(f"Reading .env file: {dot_env_file}")
            env_vars = read_dot_env_file(dot_env_file)
        else:
            logger.info(f".env file not found: {dot_env_file}.")
            env_vars = {}

        # Merge execution context environment variables
        env_vars.update(self.execution_context.env_vars)
        # Update the execution context with the merged environment variables to ensure they are available for subsequent steps
        self.execution_context.env_vars.update(env_vars)

        # Get generate-all option and detect OS
        generate_all = self.execution_context.get_input("generate-all") or False
        is_windows = platform.system() == "Windows"

        # Generate Windows scripts if on Windows OR generate-all is True
        if is_windows or generate_all:
            bat_script = self.output_dir.joinpath("env_setup.bat")
            BatEnvSetupScriptGenerator(
                install_dirs=self.execution_context.install_dirs,
                environment=env_vars,
                output_file=bat_script,
            ).to_file()
            self._generated_scripts.append(bat_script)

            ps1_script = self.output_dir.joinpath("env_setup.ps1")
            Ps1EnvSetupScriptGenerator(
                install_dirs=self.execution_context.install_dirs,
                environment=env_vars,
                output_file=ps1_script,
            ).to_file()
            self._generated_scripts.append(ps1_script)

        # Generate Unix/Linux/macOS script if NOT on Windows OR generate-all is True
        if not is_windows or generate_all:
            sh_script = self.output_dir.joinpath("env_setup.sh")
            ShEnvSetupScriptGenerator(
                install_dirs=self.execution_context.install_dirs,
                environment=env_vars,
                output_file=sh_script,
            ).to_file()
            self._generated_scripts.append(sh_script)

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return self._generated_scripts

    def get_name(self) -> str:
        return self.__class__.__name__

    def update_execution_context(self) -> None:
        pass

    def get_needs_dependency_management(self) -> bool:
        return False
