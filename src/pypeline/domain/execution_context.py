import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.data_registry import DataRegistry
from py_app_dev.core.subprocess import SubprocessExecutor

from .artifacts import ProjectArtifactsLocator


@dataclass
class ExecutionContext:
    project_root_dir: Path
    # Keep track of all install directories, updated by any step for the subsequent steps
    install_dirs: List[Path] = field(default_factory=list)
    # Data registry to exchange data of any type
    data_registry: DataRegistry = field(default_factory=DataRegistry)
    # Inputs provided for the pipeline run
    inputs: Dict[str, Any] = field(default_factory=dict)

    def add_install_dirs(self, install_dirs: List[Path]) -> None:
        self.install_dirs.extend(install_dirs)

    def create_process_executor(self, command: List[str | Path], cwd: Optional[Path] = None) -> SubprocessExecutor:
        # Add the install directories to the PATH
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join([path.absolute().as_posix() for path in self.install_dirs] + [env["PATH"]])
        # When started from a windows shell (e.g. cmd on Jenkins) the shell parameter must be set to True
        shell = True if os.name == "nt" else False
        return SubprocessExecutor(command, cwd=cwd, env=env, shell=shell)

    def create_artifacts_locator(self) -> ProjectArtifactsLocator:
        return ProjectArtifactsLocator(self.project_root_dir)
