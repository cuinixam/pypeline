from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from .pipeline import PipelineConfig

InputType = Literal["string", "integer", "boolean"]


@dataclass
class ProjectInput(DataClassDictMixin):
    """Represents a single input parameter for a pipeline step similar to GitHub workflows inputs."""

    type: InputType
    description: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False


@dataclass
class ProjectConfig(DataClassDictMixin):
    pipeline: PipelineConfig
    inputs: Optional[Dict[str, ProjectInput]] = None
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Optional[Path] = None

    @classmethod
    def from_file(cls, config_file: Path) -> "ProjectConfig":
        config_dict = cls.parse_to_dict(config_file)
        try:
            return cls.from_dict(config_dict)
        except Exception as e:
            raise UserNotificationException(f"Invalid configuration file '{config_file}'. \nError: {e}") from None

    @staticmethod
    def parse_to_dict(config_file: Path) -> Dict[str, Any]:
        try:
            with open(config_file) as fs:
                config_dict = yaml.safe_load(fs)
                # Add file name to config to keep track of where configuration was loaded from
                config_dict["file"] = config_file
            return config_dict
        except ScannerError as e:
            raise UserNotificationException(f"Failed scanning configuration file '{config_file}'. \nError: {e}") from None
        except ParserError as e:
            raise UserNotificationException(f"Failed parsing configuration file '{config_file}'. \nError: {e}") from None
