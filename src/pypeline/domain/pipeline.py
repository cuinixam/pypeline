import importlib
from abc import abstractmethod
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    OrderedDict,
    Protocol,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
)

from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
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
    #: Command to run. For simple steps that don't need a class. Example: run: [echo, 'Hello World!']
    run: Optional[Union[str, List[str]]] = None
    #: Step description
    description: Optional[str] = None
    #: Step timeout in seconds
    timeout_sec: Optional[int] = None
    #: Custom step configuration
    config: Optional[Dict[str, Any]] = None


PipelineConfig: TypeAlias = Union[List[PipelineStepConfig], OrderedDict[str, List[PipelineStepConfig]]]

TPipelineStep = TypeVar("TPipelineStep", covariant=True)


@dataclass
class PipelineStepReference(Generic[TPipelineStep]):
    """Once a Step is found, keep the Step class reference to be able to instantiate it later."""

    group_name: Optional[str]
    _class: Type[TPipelineStep]
    config: Optional[Dict[str, Any]] = None

    @property
    def name(self) -> str:
        return self._class.__name__


class PipelineConfigIterator:
    """
    Iterates over the pipeline configuration, yielding group name and steps configuration.

    This class abstracts the iteration logic for PipelineConfig, which can be:
    - A list of steps (group name is None)
    - An OrderedDict with group names as keys and lists of steps as values.

    The iterator yields tuples of (group_name, steps).
    """

    def __init__(self, pipeline_config: PipelineConfig) -> None:
        self._items = pipeline_config.items() if isinstance(pipeline_config, OrderedDict) else [(None, pipeline_config)]

    def __iter__(self) -> Iterator[Tuple[Optional[str], List[PipelineStepConfig]]]:
        """Return an iterator."""
        yield from self._items


class StepClassFactory(Generic[TPipelineStep], Protocol):
    def create_step_class(self, step_config: PipelineStepConfig, project_root_dir: Path) -> Type[TPipelineStep]: ...


class PipelineLoader(Generic[TPipelineStep]):
    def __init__(self, pipeline_config: PipelineConfig, project_root_dir: Path, step_class_factory: Optional[StepClassFactory[TPipelineStep]] = None) -> None:
        self.pipeline_config = pipeline_config
        self.project_root_dir = project_root_dir
        self.step_class_factory = step_class_factory

    def load_steps_references(self) -> List[PipelineStepReference[TPipelineStep]]:
        result = []
        for group_name, steps_config in PipelineConfigIterator(self.pipeline_config):
            result.extend(self._load_steps(group_name, steps_config, self.project_root_dir, self.step_class_factory))
        return result

    @staticmethod
    def _load_steps(
        group_name: Optional[str], steps_config: List[PipelineStepConfig], project_root_dir: Path, step_class_factory: Optional[StepClassFactory[TPipelineStep]] = None
    ) -> List[PipelineStepReference[TPipelineStep]]:
        result = []
        for step_config in steps_config:
            step_class_name = step_config.class_name or step_config.step
            if step_config.module:
                step_class = PipelineLoader[TPipelineStep]._load_module_step(step_config.module, step_class_name)
            elif step_config.file:
                step_class = PipelineLoader[TPipelineStep]._load_user_step(project_root_dir.joinpath(step_config.file), step_class_name)
            else:
                if step_class_factory:
                    step_class = step_class_factory.create_step_class(step_config, project_root_dir)
                else:
                    raise UserNotificationException(
                        f"Step '{step_class_name}' has no 'module' nor 'file' defined nor a custom step class factory was provided. Please check your pipeline configuration."
                    )
            result.append(PipelineStepReference(group_name, step_class, step_config.config))
        return result

    @staticmethod
    def _load_user_step(python_file: Path, step_class_name: str) -> Type[TPipelineStep]:
        # Create a module specification from the file path
        spec = spec_from_file_location(f"user__{python_file.stem}", python_file)
        if spec and spec.loader:
            step_module = module_from_spec(spec)
            # Import the module
            spec.loader.exec_module(step_module)
            try:
                step_class = getattr(step_module, step_class_name)
            except AttributeError:
                raise UserNotificationException(f"Could not load class '{step_class_name}' from file '{python_file}'. Please check your pipeline configuration.") from None
            return step_class
        raise UserNotificationException(f"Could not load file '{python_file}'. Please check the file for any errors.")

    @staticmethod
    def _load_module_step(module_name: str, step_class_name: str) -> Type[TPipelineStep]:
        try:
            module = importlib.import_module(module_name)
            step_class = getattr(module, step_class_name)
        except ImportError:
            raise UserNotificationException(f"Could not load module '{module_name}'. Please check your pipeline configuration.") from None
        except AttributeError:
            raise UserNotificationException(f"Could not load class '{step_class_name}' from module '{module_name}'. Please check your pipeline configuration.") from None
        return step_class


TExecutionContext = TypeVar("TExecutionContext", bound=ExecutionContext)


class PipelineStep(Generic[TExecutionContext], Runnable):
    """One can create subclasses of PipelineStep that specify the type of ExecutionContext they require."""

    def __init__(self, execution_context: TExecutionContext, group_name: Optional[str], config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(self.get_needs_dependency_management())
        self.execution_context = execution_context
        self.group_name = group_name
        self.config = config
        self.project_root_dir = self.execution_context.project_root_dir

    @property
    def output_dir(self) -> Path:
        output_dir = self.execution_context.create_artifacts_locator().build_dir
        if self.group_name:
            output_dir = output_dir / self.group_name
        return output_dir

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
