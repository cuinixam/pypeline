import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from py_app_dev.core.data_registry import DataRegistry
from py_app_dev.core.subprocess import SubprocessExecutor

from .artifacts import ProjectArtifactsLocator

DEFAULT_INSTALL_DIR_ORDER = 50


@dataclass
class InstallDir:
    path: Path
    # Lower orders come first in PATH
    order: int = DEFAULT_INSTALL_DIR_ORDER


@dataclass
class ExecutionContext:
    project_root_dir: Path
    # Install directories mapped to their PATH order. The dict keeps the registration order and each directory once.
    _install_dirs: Dict[Path, int] = field(default_factory=dict, init=False, repr=False)
    # Data registry to exchange data of any type
    data_registry: DataRegistry = field(default_factory=DataRegistry)
    # Inputs provided for the pipeline run
    inputs: Dict[str, Any] = field(default_factory=dict)
    # Environment variables to be passed to the subprocesses
    env_vars: Dict[str, Any] = field(default_factory=dict)

    def get_input(self, name: str) -> Optional[Any]:
        return self.inputs.get(name, None)

    @property
    def install_dirs(self) -> Tuple[Path, ...]:
        # The sort is stable, so directories with the same order keep their registration order
        return tuple(sorted(self._install_dirs, key=self._install_dirs.__getitem__))

    def add_install_dirs(self, install_dirs: Sequence[Path | InstallDir]) -> None:
        """Register directories to be added to the PATH of the subsequent steps. A plain path gets the default order."""
        for install_dir in install_dirs:
            if not isinstance(install_dir, InstallDir):
                install_dir = InstallDir(install_dir)
            # A directory registered more than once keeps its lowest order, so a later registration cannot push it back
            self._install_dirs[install_dir.path] = min(self._install_dirs.get(install_dir.path, install_dir.order), install_dir.order)

    def add_env_vars(self, env_vars: Dict[str, Any]) -> None:
        self.env_vars.update(env_vars)

    def create_process_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PATH"] = os.pathsep.join([path.absolute().as_posix() for path in self.install_dirs] + [env["PATH"]])
        return env

    def create_process_executor(self, command: List[str | Path], cwd: Optional[Path] = None) -> SubprocessExecutor:
        # When started from a windows shell (e.g. cmd on Jenkins) the shell parameter must be set to True
        shell = True if os.name == "nt" else False
        return SubprocessExecutor(command, cwd=cwd, env=self.create_process_env(), shell=shell)

    def create_artifacts_locator(self) -> ProjectArtifactsLocator:
        return ProjectArtifactsLocator(self.project_root_dir)
