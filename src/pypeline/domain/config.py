from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from py_app_dev.core.config import ConfigElement, parse_config_element

from .pipeline import PipelineConfig

InputType = Literal["string", "integer", "boolean"]


@dataclass
class ProjectInput(ConfigElement):
    """Represents a single input parameter for a pipeline step similar to GitHub workflows inputs."""

    type: InputType
    description: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False


@dataclass
class ProjectConfig(ConfigElement):
    pipeline: PipelineConfig
    inputs: Optional[Dict[str, ProjectInput]] = None

    @property
    def file(self) -> Optional[Path]:
        """The file this configuration was loaded from (None for in-memory configs)."""
        return self.location.file if self.location else None

    @classmethod
    def from_file(cls, config_file: Path) -> "ProjectConfig":
        if not config_file.is_file():
            raise FileNotFoundError(config_file)
        return parse_config_element(cls, config_file)
