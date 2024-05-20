import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from py_app_dev.core.subprocess import SubprocessExecutor

from .artifacts import ProjectArtifactsLocator


@dataclass
class ExecutionContext:
    project_root_dir: Path
    # Keep track of all install directories, updated by any step for the subsequent steps
    install_dirs: List[Path] = field(default_factory=list)
    # Keep track of the environment variables, updated by any step for the subsequent steps
    env_vars: Dict[str, Any] = field(default_factory=dict)

    def add_install_dirs(self, install_dirs: List[Path]) -> None:
        self.install_dirs.extend(install_dirs)

    def add_env_vars(self, env_vars: Dict[str, Any]) -> None:
        self.env_vars.update(env_vars)

    def create_process_executor(self, command: List[str | Path], cwd: Optional[Path] = None) -> SubprocessExecutor:
        # Add the install directories to the PATH
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PATH"] = os.pathsep.join([path.absolute().as_posix() for path in self.install_dirs] + [env["PATH"]])
        return SubprocessExecutor(command, cwd=cwd, env=env, shell=True)  # noqa: S604

    def create_artifacts_locator(self) -> ProjectArtifactsLocator:
        return ProjectArtifactsLocator(self.project_root_dir)
