from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    OrderedDict,
    Type,
    TypeAlias,
    TypeVar,
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

TExecutionContext = TypeVar("TExecutionContext", bound=ExecutionContext)


class PipelineStep(Generic[TExecutionContext], Runnable):
    """One can create subclasses of PipelineStep that specify the type of ExecutionContext they require."""

    def __init__(self, execution_context: TExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(self.get_needs_dependency_management())
        self.execution_context = execution_context
        self.group_name = group_name
        self.config = config
        self.project_root_dir = self.execution_context.project_root_dir

    @property
    def output_dir(self) -> Path:
        return self.execution_context.create_artifacts_locator().build_dir.joinpath(self.group_name)

    @abstractmethod
    def update_execution_context(self) -> None:
        """
        Even if the step does not need to run ( because it is not outdated ), it can still update the execution context.

        A typical use case is for steps installing software that need to provide the install directories in the execution context even if all tools are already installed.
        """
        pass

    def get_needs_dependency_management(self) -> bool:
        """If false, the step executor will not check for outdated dependencies. This is useful for steps consisting of command lines which shall always run."""
        return True


class PipelineStepReference(Generic[TExecutionContext]):
    def __init__(self, group_name: str, _class: Type[PipelineStep[TExecutionContext]], config: Optional[Dict[str, Any]] = None) -> None:
        self.group_name = group_name
        self._class = _class
        self.config = config

    @property
    def name(self) -> str:
        return self._class.__name__
