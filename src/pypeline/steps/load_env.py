from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.logging import logger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


class LoadEnv(PipelineStep):
    """Load the environment variables from the .env file."""

    def __init__(self, execution_context: ExecutionContext, output_dir: Path, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, output_dir, config)
        self.logger = logger.bind()
        self.artifacts_locator = execution_context.create_artifacts_locator()
        self.execution_context = execution_context

    def get_needs_dependency_management(self) -> bool:
        """No need to manage dependencies. The .env file is always read."""
        return False

    def run(self) -> int:
        """No need to run anything, the environment variables are loaded by update_execution_context."""
        return 0

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        """Load the environment variables from the .env file if exists."""
        env_file = self.project_root_dir.joinpath(".env")
        if env_file.exists():
            self.logger.info(f"Load environment variables from {env_file}")
            self.execution_context.add_env_vars(self.load_dot_env_file(env_file))
        else:
            self.logger.warning(f"No .env file found at {env_file}")

    @staticmethod
    def load_dot_env_file(env_file: Path) -> Dict[str, str]:
        env_vars = {}
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars
