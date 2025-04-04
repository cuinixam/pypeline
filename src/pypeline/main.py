import sys
from pathlib import Path
from typing import List, Optional

import typer
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger, time_it

from pypeline import __version__
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineConfigIterator
from pypeline.domain.project_slurper import ProjectSlurper
from pypeline.inputs_parser import InputsParser
from pypeline.kickstart.create import KickstartProject
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor

package_name = "pypeline"

app = typer.Typer(
    name=package_name, help="Configure and execute pipelines with Python (similar to GitHub workflows or Jenkins pipelines).", no_args_is_help=True, add_completion=False
)


@app.callback(invoke_without_command=True)
def version(
    version: bool = typer.Option(None, "--version", "-v", is_eager=True, help="Show version and exit."),
) -> None:
    if version:
        typer.echo(f"{package_name} {__version__}")
        raise typer.Exit()


@app.command()
@time_it("init")
def init(
    project_dir: Path = typer.Option(Path.cwd().absolute(), help="The project directory"),  # noqa: B008
    force: bool = typer.Option(False, help="Force the initialization of the project even if the directory is not empty."),
) -> None:
    KickstartProject(project_dir, force).run()


@app.command()
@time_it("run")
def run(
    project_dir: Path = typer.Option(Path.cwd().absolute(), help="The project directory"),  # noqa: B008,
    config_file: Optional[str] = typer.Option(None, help="The name of the YAML configuration file containing the pypeline definition."),
    step: Optional[List[str]] = typer.Option(None, help="Name of the step to run (as written in the pipeline config)."),  # noqa: B008
    single: bool = typer.Option(False, help="If provided, only the provided step will run, without running all previous steps in the pipeline."),
    print: bool = typer.Option(False, help="Print the pipeline steps."),
    force_run: bool = typer.Option(False, help="Force the execution of a step even if it is not dirty."),
    dry_run: bool = typer.Option(False, help="Do not run any step, just print the steps that would be executed."),
    inputs: Optional[List[str]] = typer.Option(  # noqa: B008
        None,
        "--input",
        "-i",
        help="Provide input parameters as key=value pairs (e.g., -i name=value -i flag=true).",
    ),
) -> None:
    project_slurper = ProjectSlurper(project_dir, config_file)
    if print:
        logger.info("Pipeline steps:")
        for group, step_configs in PipelineConfigIterator(project_slurper.pipeline):
            if group:
                logger.info(f"    Group: {group}")
            for step_config in step_configs:
                logger.info(f"        {step_config.step}")
        return
    if not project_slurper.pipeline:
        raise UserNotificationException("No pipeline found in the configuration.")
    # Schedule the steps to run
    steps_references = PipelineScheduler[ExecutionContext](project_slurper.pipeline, project_dir).get_steps_to_run(step, single)
    if not steps_references:
        logger.info("No steps to run.")
        return
    # Parse the inputs
    input_definitions = project_slurper.project_config.inputs
    if input_definitions is None and inputs:
        raise UserNotificationException(f"Inputs are not accepted because there are no inputs defined in the '{project_slurper.project_config.file}' configuration.")
    if input_definitions and inputs:
        inputs_dict = InputsParser.from_inputs_definitions(input_definitions).parse_inputs(inputs)
    else:
        inputs_dict = {}
    PipelineStepsExecutor[ExecutionContext](ExecutionContext(project_dir, inputs=inputs_dict), steps_references, force_run, dry_run).run()


def main() -> None:
    try:
        setup_logger()
        app()
    except UserNotificationException as e:
        logger.error(f"{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
