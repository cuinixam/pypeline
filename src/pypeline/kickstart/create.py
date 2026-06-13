import shutil
import sys
from pathlib import Path
from typing import List, Optional, Union

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger


class ProjectBuilder:
    def __init__(self, project_dir: Path, input_dir: Optional[Path] = None) -> None:
        self.project_dir = project_dir
        self.input_dir = input_dir if input_dir else Path(__file__).parent.joinpath("templates")

        self.dirs: List[Path] = []
        self.check_target_directory_flag = True

    def with_disable_target_directory_check(self) -> "ProjectBuilder":
        self.check_target_directory_flag = False
        return self

    def with_dir(self, dir: Union[Path, str]) -> "ProjectBuilder":
        self.dirs.append(self.resolve_file_path(dir))
        return self

    def resolve_file_paths(self, files: List[Path | str]) -> List[Path]:
        return [self.resolve_file_path(file) for file in files]

    def resolve_file_path(self, file: Union[Path, str]) -> Path:
        return self.input_dir.joinpath(file) if isinstance(file, str) else file

    @staticmethod
    def _check_target_directory(project_dir: Path) -> None:
        if project_dir.is_dir() and any(project_dir.iterdir()):
            raise UserNotificationException(f"Project directory '{project_dir}' is not empty. Use --force to override.")

    def build(self) -> None:
        if self.check_target_directory_flag:
            self._check_target_directory(self.project_dir)
        for dir in self.dirs:
            shutil.copytree(dir, self.project_dir, dirs_exist_ok=True)


class KickstartProject:
    def __init__(self, project_dir: Path, force: bool = False) -> None:
        self.logger = logger.bind()
        self.project_dir = project_dir
        self.force = force

    def run(self) -> None:
        self.logger.info(f"Kickstart new project in '{self.project_dir.absolute().as_posix()}'")
        project_builder = ProjectBuilder(self.project_dir)
        if self.force:
            project_builder.with_disable_target_directory_check()
        project_builder.with_dir("project")
        project_builder.build()
        self._pin_python_version()

    def _pin_python_version(self) -> None:
        """Pin the generated config's python_version to the interpreter running `init`, so the bootstrap env is stable."""
        config_file = self.project_dir / "pypeline.yaml"
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        config_file.write_text(config_file.read_text().replace("{{PYTHON_VERSION}}", version))
