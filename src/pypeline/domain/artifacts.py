import sys
from pathlib import Path
from typing import List, Optional

from py_app_dev.core.exceptions import UserNotificationException

CONFIG_FILENAME = "pypeline.yaml"


class ProjectArtifactsLocator:
    """Provides paths to project artifacts."""

    def __init__(self, project_root_dir: Path, config_file: Optional[str] = None) -> None:
        self.project_root_dir = project_root_dir
        self.build_dir = project_root_dir / "build"
        self.config_file = project_root_dir.joinpath(config_file if config_file else CONFIG_FILENAME)
        self.external_dependencies_dir = self.build_dir / "external"
        scripts_dir = "Scripts" if sys.platform.startswith("win32") else "bin"
        self.venv_scripts_dir = self.project_root_dir.joinpath(".venv").joinpath(scripts_dir)

    def locate_artifact(self, artifact: str, first_search_paths: List[Optional[Path]]) -> Path:
        search_paths = []
        for path in first_search_paths:
            if path:
                search_paths.append(path.parent if path.is_file() else path)
        for dir in [
            *search_paths,
            self.project_root_dir,
        ]:
            if dir and (artifact_path := Path(dir).joinpath(artifact)).exists():
                return artifact_path
        else:
            raise UserNotificationException(f"Artifact '{artifact}' not found in the project.")
