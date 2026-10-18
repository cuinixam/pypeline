from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Union

from py_app_dev.core.config import ConfigElement, parse_config_element
from py_app_dev.core.exceptions import UserNotificationException

from .pipeline import IncludeSpec, PipelineConfig, PipelineConfigIterator, PipelineStepConfig

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
        config = parse_config_element(cls, config_file)
        config.pipeline = assemble_pipeline(config.pipeline, config_file)
        return config

    @classmethod
    def _load(cls, config_file: Path, visited: Set[Path]) -> "ProjectConfig":
        """Load an included fragment. Unlike ``from_file`` it carries the include chain, to detect cycles."""
        resolved = config_file.resolve()
        if resolved in visited:
            chain = " -> ".join(str(path) for path in (*visited, resolved))
            raise UserNotificationException(f"Circular pipeline include detected: {chain}")
        config = parse_config_element(cls, config_file)
        # Pin each step's output group to THIS file before inserting any included steps, so an
        # included step keeps the group of the file it is defined in, not the one it is included into.
        _stamp_home_groups(config.pipeline)
        config.pipeline = _expand_includes(config.pipeline, config_file, visited | {resolved})
        return config



def assemble_pipeline(pipeline: PipelineConfig, source_file: Path) -> PipelineConfig:
    """
    Expand the ``include:`` entries of a pipeline parsed from ``source_file``.

    For applications that parse their own configuration file and reuse only the pipeline
    model; :meth:`ProjectConfig.from_file` is this plus pypeline's own schema. An absolute
    include path is used as given, so a caller may resolve paths itself.
    """
    _stamp_home_groups(pipeline)
    return _expand_includes(pipeline, source_file, {source_file.resolve()})


def _expand_includes(pipeline: PipelineConfig, including_file: Path, visited: Set[Path]) -> PipelineConfig:
    if isinstance(pipeline, OrderedDict):
        return OrderedDict((group, _expand_steps(steps, including_file, visited)) for group, steps in pipeline.items())
    return _expand_steps(pipeline, including_file, visited)


def _expand_steps(steps: List[PipelineStepConfig], including_file: Path, visited: Set[Path]) -> List[PipelineStepConfig]:
    result: List[PipelineStepConfig] = []
    for entry in steps:
        _validate_entry(entry, including_file)
        if entry.include is None:
            result.append(entry)
        else:
            result.extend(_expand_include(entry.include, including_file, visited))
    return result


def _expand_include(include: Union[str, IncludeSpec], including_file: Path, visited: Set[Path]) -> List[PipelineStepConfig]:
    # A plain string includes the whole file; an IncludeSpec narrows it to named steps. Coerce to the
    # object form here so the rest reads one shape, without normalising the config's genuine union away.
    spec = include if isinstance(include, IncludeSpec) else IncludeSpec(file=include)
    included_file = including_file.parent / spec.file
    # Raise here, not as FileNotFoundError: callers map that to "<outer file> not found", which hides the missing include.
    if not included_file.is_file():
        raise UserNotificationException(f"Included pipeline file '{included_file}' not found (included from '{including_file}').")
    fragment = ProjectConfig._load(included_file, visited)
    if isinstance(fragment.pipeline, OrderedDict):
        raise UserNotificationException(
            f"Included pipeline '{spec.file}' must define a flat list of steps (no groups) to be included from '{including_file}'."
        )
    steps = fragment.pipeline
    if spec.steps is None:
        return steps
    available = [step.step for step in steps]
    unknown = [name for name in spec.steps if name not in available]
    if unknown:
        raise UserNotificationException(f"Included pipeline '{spec.file}' has no step(s) {unknown}. Available steps: {available}.")
    # The selection list dictates execution order; a name listed twice runs the step twice.
    by_name = {step.step: step for step in steps}
    return [by_name[name] for name in spec.steps]

def _stamp_home_groups(pipeline: PipelineConfig) -> None:
    for group_name, steps in PipelineConfigIterator(pipeline):
        for step in steps:
            step.set_home_group(group_name)


def _validate_entry(entry: PipelineStepConfig, including_file: Path) -> None:
    where = entry.location or including_file
    if entry.include is not None and any((entry.step, entry.module, entry.file, entry.run)):
        raise UserNotificationException(f"Pipeline entry at {where} defines both 'include' and a step; an include entry must stand alone.")
    if entry.include is None and entry.step is None:
        raise UserNotificationException(f"Pipeline entry at {where} must define either a 'step' or an 'include'.")
