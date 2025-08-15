from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    OrderedDict,
    Tuple,
    Type,
)

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.core.runnable import Executor

from .domain.artifacts import ProjectArtifactsLocator
from .domain.execution_context import ExecutionContext
from .domain.pipeline import PipelineConfig, PipelineConfigIterator, PipelineLoader, PipelineStep, PipelineStepConfig, PipelineStepReference, StepClassFactory, TExecutionContext


class RunCommandClassFactory(StepClassFactory[PipelineStep[TExecutionContext]]):
    def create_step_class(self, step_config: PipelineStepConfig, project_root_dir: Path) -> Type[PipelineStep[ExecutionContext]]:
        _ = project_root_dir  # Unused because we do not need to locate files relative to the project root directory
        step_name = step_config.class_name or step_config.step
        if step_config.run:
            # We want the run field to always return a list of strings (the command and its arguments).
            run_command = step_config.run.split(" ") if isinstance(step_config.run, str) else step_config.run
            return self._create_run_command_step_class(run_command, step_name)
        raise UserNotificationException(f"Step '{step_name}' has `run` command defined. Please check your pipeline configuration.")

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
        steps_references: List[PipelineStepReference[PipelineStep[TExecutionContext]]],
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

    def get_steps_to_run(self, step_names: Optional[List[str]] = None, single: bool = False) -> List[PipelineStepReference[PipelineStep[TExecutionContext]]]:
        return self.create_pipeline_loader(self.filter_steps(self.pipeline, step_names, single), self.project_root_dir).load_steps_references()

    @staticmethod
    def filter_steps(pipeline_config: PipelineConfig, step_names: Optional[List[str]], single: bool) -> PipelineConfig:
        """
        Filters the pipeline steps based on the provided step names.

        If no step names are provided, all steps are returned.
        When `single` is True, only the named steps are returned, otherwise all steps up to the last named step are returned.
        """
        if not step_names:
            return pipeline_config

        step_names_set = set(step_names)
        filtered_groups: List[Tuple[Optional[str], List[PipelineStepConfig]]] = []
        found_steps: set[str] = set()

        for group_name, steps_config in PipelineConfigIterator(pipeline_config):
            filtered_steps = PipelineScheduler._filter_steps_in_group(steps_config, step_names_set, single, found_steps)

            if filtered_steps:
                filtered_groups.append((group_name, filtered_steps))

            if not single and found_steps == step_names_set:
                break

        missing_steps = step_names_set - found_steps
        if missing_steps:
            raise UserNotificationException(f"Steps not found in pipeline configuration: {', '.join(missing_steps)}")

        return PipelineScheduler._create_pipeline_config_from_groups(filtered_groups)

    @staticmethod
    def _filter_steps_in_group(steps_config: List[PipelineStepConfig], step_names_set: set[str], single: bool, found_steps: set[str]) -> List[PipelineStepConfig]:
        """Filter steps within a single group."""
        filtered_steps = []

        for step_config in steps_config:
            step_name = step_config.class_name or step_config.step

            if single:
                if step_name in step_names_set:
                    filtered_steps.append(step_config)
                    found_steps.add(step_name)
            else:
                filtered_steps.append(step_config)
                if step_name in step_names_set:
                    found_steps.add(step_name)
                    if found_steps == step_names_set:
                        break

        return filtered_steps

    @staticmethod
    def _create_pipeline_config_from_groups(groups: List[Tuple[Optional[str], List[PipelineStepConfig]]]) -> PipelineConfig:
        """Create a PipelineConfig from filtered groups."""
        if not groups:
            return []

        # If all groups have None as group_name, return a simple list
        if all(group_name is None for group_name, _ in groups):
            return [step for _, steps in groups for step in steps]

        # Otherwise, return an OrderedDict
        result: OrderedDict[str, List[PipelineStepConfig]] = OrderedDict()
        for group_name, steps in groups:
            if group_name is not None:
                result[group_name] = steps

        return result

    @staticmethod
    def create_pipeline_loader(pipeline: PipelineConfig, project_root_dir: Path) -> PipelineLoader[PipelineStep[TExecutionContext]]:
        return PipelineLoader[PipelineStep[TExecutionContext]](pipeline, project_root_dir, RunCommandClassFactory())
