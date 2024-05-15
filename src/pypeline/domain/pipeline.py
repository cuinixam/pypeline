from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    OrderedDict,
    Type,
    TypeAlias,
)

from mashumaro import DataClassDictMixin
from py_app_dev.core.runnable import Runnable

from .execution_context import ExecutionContext


@dataclass
class PipelineStepConfig(DataClassDictMixin):
    #: Step name or class name if file is not specified
    step: str
    #: Path to file with step class
    file: Optional[str] = None
    #: Python module with step class
    module: Optional[str] = None
    #: Step class name
    class_name: Optional[str] = None
    #: Command to run. For simple steps that don't need a class
    run: Optional[str] = None
    #: Step description
    description: Optional[str] = None
    #: Step timeout in seconds
    timeout_sec: Optional[int] = None
    #: Custom step configuration
    config: Optional[Dict[str, Any]] = None


PipelineConfig: TypeAlias = OrderedDict[str, List[PipelineStepConfig]]


class PipelineStep(Runnable):
    def __init__(self, execution_context: ExecutionContext, output_dir: Path, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(self.get_needs_dependency_management())
        self.execution_context = execution_context
        self.output_dir = output_dir
        self.config = config
        self.project_root_dir = self.execution_context.project_root_dir

    @abstractmethod
    def update_execution_context(self) -> None:
        pass

    def get_needs_dependency_management(self) -> bool:
        return True


class PipelineStepReference:
    def __init__(self, group_name: str, _class: Type[PipelineStep], config: Optional[Dict[str, Any]] = None) -> None:
        self.group_name = group_name
        self._class = _class
        self.config = config

    @property
    def name(self) -> str:
        return self._class.__name__
