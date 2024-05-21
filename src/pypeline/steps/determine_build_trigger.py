from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.logging import logger

from pypeline.domain.build_trigger import BuildTrigger

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStepThatOnlyUpdatesTheExecutionContext


class DetermineBuildTrigger(PipelineStepThatOnlyUpdatesTheExecutionContext):
    def __init__(self, execution_context: ExecutionContext, output_dir: Path, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, output_dir, config)
        self.logger = logger.bind()
        self.artifacts_locator = execution_context.create_artifacts_locator()

    def update_execution_context(self) -> None:
        """Determine the build trigger based on the environment variables."""
        self.execution_context.build_trigger = self.determine_build_trigger()

    def determine_build_trigger(self) -> BuildTrigger:
        """
        Determine the build trigger based on the environment variables.

        In case the 'JENKINS_URL' environment variable is set, the build is triggered by Jenkins.
        Otherwise, the build is triggered by a local user.
        """
        pass
