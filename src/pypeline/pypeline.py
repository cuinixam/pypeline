import importlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    cast,
)

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.core.runnable import Executor

from .domain.artifacts import ProjectArtifactsLocator
from .domain.execution_context import ExecutionContext
from .domain.pipeline import PipelineConfig, PipelineConfigIterator, PipelineStep, PipelineStepConfig, PipelineStepReference, TExecutionContext


class PipelineLoader(Generic[TExecutionContext]):
    """
    Loads pipeline steps from a pipeline configuration.

    The steps are not instantiated, only the references are returned (lazy load).
    The pipeline loader needs to know the project root directory to be able to find the
    user custom local steps.
    """

    def __init__(self, pipeline_config: PipelineConfig, project_root_dir: Path) -> None:
        self.pipeline_config = pipeline_config
        self.project_root_dir = project_root_dir

    def load_steps_references(self) -> List[PipelineStepReference[TExecutionContext]]:
        result = []
        for group_name, steps_config in PipelineConfigIterator(self.pipeline_config):
            result.extend(self._load_steps(group_name, steps_config, self.project_root_dir))
        return result

    @staticmethod
    def _load_steps(
        group_name: Optional[str],
        steps_config: List[PipelineStepConfig],
        project_root_dir: Path,
    ) -> List[PipelineStepReference[TExecutionContext]]:
        result = []
        for step_config in steps_config:
            step_class_name = step_config.class_name or step_config.step
            if step_config.module:
                step_class = PipelineLoader._load_module_step(step_config.module, step_class_name)
            elif step_config.file:
                step_class = PipelineLoader._load_user_step(project_root_dir.joinpath(step_config.file), step_class_name)
            elif step_config.run:
                # We want the run field to always return a list of strings (the command and its arguments).
                run_command = step_config.run.split(" ") if isinstance(step_config.run, str) else step_config.run
                step_class = PipelineLoader._create_run_command_step_class(run_command, step_class_name)
            else:
                raise UserNotificationException(f"Step '{step_class_name}' has no 'module' nor 'file' nor `run` defined. Please check your pipeline configuration.")
            result.append(PipelineStepReference[TExecutionContext](group_name, cast(Type[PipelineStep[TExecutionContext]], step_class), step_config.config))
        return result

    @staticmethod
    def _load_user_step(python_file: Path, step_class_name: str) -> Type[PipelineStep[ExecutionContext]]:
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
    def _load_module_step(module_name: str, step_class_name: str) -> Type[PipelineStep[ExecutionContext]]:
        try:
            module = importlib.import_module(module_name)
            step_class = getattr(module, step_class_name)
        except ImportError:
            raise UserNotificationException(f"Could not load module '{module_name}'. Please check your pipeline configuration.") from None
        except AttributeError:
            raise UserNotificationException(f"Could not load class '{step_class_name}' from module '{module_name}'. Please check your pipeline configuration.") from None
        return step_class

    @staticmethod
    def _create_run_command_step_class(command: List[str], name: str) -> Type[PipelineStep[ExecutionContext]]:
        """Dynamically creates a step class for a given command."""

        class TmpDynamicRunCommandStep(PipelineStep[ExecutionContext]):
            """A simple step that runs a command."""

            def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
                super().__init__(execution_context, group_name, config)
                self.command = command
                self.name = name

            def get_needs_dependency_management(self) -> bool:
                """A command step does not need dependency management."""
                return False

            def run(self) -> int:
                self.execution_context.create_process_executor(
                    # We have to disable type checking for the command because mypy considers that a List[str] is not compatible with a List[Union[str, Path]] :(
                    self.command,  # type: ignore
                    cwd=self.project_root_dir,
                ).execute()
                return 0

            def get_name(self) -> str:
                return self.name

            def get_inputs(self) -> List[Path]:
                return []

            def get_outputs(self) -> List[Path]:
                return []

            def update_execution_context(self) -> None:
                pass

        # Dynamically create the class with the given name
        return type(name, (TmpDynamicRunCommandStep,), {})


class PipelineStepsExecutor(Generic[TExecutionContext]):
    """Executes a list of pipeline steps sequentially."""

    def __init__(
        self,
        execution_context: TExecutionContext,
        steps_references: List[PipelineStepReference[TExecutionContext]],
        force_run: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.logger = logger.bind()
        self.execution_context = execution_context
        self.steps_references = steps_references
        self.force_run = force_run
        self.dry_run = dry_run

    @property
    def artifacts_locator(self) -> ProjectArtifactsLocator:
        return self.execution_context.create_artifacts_locator()

    def run(self) -> None:
        for step_reference in self.steps_references:
            step = step_reference._class(self.execution_context, step_reference.group_name, step_reference.config)
            # Create the step output directory, to make sure that files can be created.
            step.output_dir.mkdir(parents=True, exist_ok=True)
            # Execute the step is necessary. If the step is not dirty, it will not be executed
            Executor(step.output_dir, self.force_run, self.dry_run).execute(step)
            # Independent if the step was executed or not, every step shall update the context
            step.update_execution_context()

        return


class PipelineScheduler(Generic[TExecutionContext]):
    """
    Schedules which steps must be executed based on the provided configuration.

    * If a step name is provided and the single flag is set, only that step will be executed.
    * If a step name is provided and the single flag is not set, all steps up to the provided step will be executed.
    * In case a command is provided, only the steps up to that command will be executed.
    * If no step name is provided, all steps will be executed.
    """

    def __init__(self, pipeline: PipelineConfig, project_root_dir: Path) -> None:
        self.pipeline = pipeline
        self.project_root_dir = project_root_dir
        self.logger = logger.bind()

    def get_steps_to_run(self, step_name: Optional[str] = None, single: bool = False) -> List[PipelineStepReference[TExecutionContext]]:
        pipeline_loader = PipelineLoader[TExecutionContext](self.pipeline, self.project_root_dir)
        return self.filter_steps_references(pipeline_loader.load_steps_references(), step_name, single)

    @staticmethod
    def filter_steps_references(
        steps_references: List[PipelineStepReference[TExecutionContext]],
        step_name: Optional[str],
        single: Optional[bool],
    ) -> List[PipelineStepReference[TExecutionContext]]:
        if step_name:
            step_reference = next((step for step in steps_references if step.name == step_name), None)
            if not step_reference:
                return []
            if single:
                return [step_reference]
            return [step for step in steps_references if steps_references.index(step) <= steps_references.index(step_reference)]
        return steps_references
