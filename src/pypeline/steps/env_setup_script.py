from pathlib import Path
from typing import Dict, List

from py_app_dev.core.env_setup_scripts import BatEnvSetupScriptGenerator, Ps1EnvSetupScriptGenerator
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


class GenerateEnvSetupScript(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        logger.info(f"Generating environment setup scripts under {self.output_dir} ...")
        # Read the .env file and set up the environment variables
        dot_env_file = self.execution_context.project_root_dir.joinpath(".env")
        if dot_env_file.exists():
            logger.debug(f"Reading .env file: {dot_env_file}")
            env_vars = read_dot_env_file(dot_env_file)
        else:
            logger.warning(f".env file not found: {dot_env_file}")
            env_vars = {}
        # Generate the environment setup scripts
        BatEnvSetupScriptGenerator(
            install_dirs=self.execution_context.install_dirs,
            environment=env_vars,
            output_file=self.output_dir.joinpath("env_setup.bat"),
        ).to_file()
        Ps1EnvSetupScriptGenerator(
            install_dirs=self.execution_context.install_dirs,
            environment=env_vars,
            output_file=self.output_dir.joinpath("env_setup.ps1"),
        ).to_file()

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def get_name(self) -> str:
        return self.__class__.__name__

    def update_execution_context(self) -> None:
        pass

    def get_needs_dependency_management(self) -> bool:
        return False
