import sys
from pathlib import Path
from typing import List, Optional

import typer
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger, time_it

from pypeline import __version__
from pypeline.domain.project_slurper import ProjectSlurper
from pypeline.kickstart.create import KickstartProject
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor

package_name = "pypeline"

app = typer.Typer(name=package_name, help="Configure and execute steps for developing a python package.", no_args_is_help=True, add_completion=False)


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
    bootstrap_only: bool = typer.Option(False, help="Initialize only the bootstrap files."),
    force: bool = typer.Option(False, help="Force the initialization of the project even if the directory is not empty."),
) -> None:
    KickstartProject(project_dir, bootstrap_only, force).run()


@app.command()
@time_it("run")
def run(
    project_dir: Path = typer.Option(Path.cwd().absolute(), help="The project directory"),  # noqa: B008,
    step: Optional[str] = typer.Option(
        None,
        help="Name of the step to run (as written in the pipeline config).",
    ),
    single: bool = typer.Option(
        False,
        help="If provided, only the provided step will run, without running all previous steps in the pipeline.",
        is_flag=True,
    ),
    print: bool = typer.Option(
        False,
        help="Print the pipeline steps.",
        is_flag=True,
    ),
    force_run: bool = typer.Option(
        False,
        help="Force the execution of a step even if it is not dirty.",
        is_flag=True,
    ),
) -> None:
    project_slurper = ProjectSlurper(project_dir)
    if print:
        logger.warning("TODO: print pipeline steps")
        logger.info("Pipeline steps:")
        for group, step_configs in project_slurper.pipeline.items():
            logger.info(f"    Group: {group}")
            for step_config in step_configs:
                logger.info(f"        {step_config.step}")
        return
    if not project_slurper.pipeline:
        raise UserNotificationException("No pipeline found in the configuration.")
    # Schedule the steps to run
    steps_references = PipelineScheduler(project_slurper.pipeline, project_dir).get_steps_to_run(step, single)
    if not steps_references:
        if step:
            raise UserNotificationException(f"Step '{step}' not found in the pipeline.")
        logger.info("No steps to run.")
        return

    PipelineStepsExecutor(
        project_slurper.artifacts_locator,
        steps_references,
        force_run,
    ).run()


def main(args: Optional[List[str]] = None) -> int:
    try:
        setup_logger()
        if args is None:
            args = sys.argv[1:]
        app(args)
        return 0
    except UserNotificationException as e:
        logger.error(f"{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
