from abc import abstractmethod
from pathlib import Path
from typing import Type

from py_app_dev.core.runnable import Runnable

from .execution_context import ExecutionContext


class PipelineStep(Runnable):
    def __init__(self, execution_context: ExecutionContext, output_dir: Path) -> None:
        self.execution_context = execution_context
        self.output_dir = output_dir
        self.project_root_dir = self.execution_context.project_root_dir

    @abstractmethod
    def update_execution_context(self) -> None:
        pass


class PipelineStepReference:
    def __init__(self, group_name: str, _class: Type[PipelineStep]) -> None:
        self.group_name = group_name
        self._class = _class

    @property
    def name(self) -> str:
        return self._class.__name__
