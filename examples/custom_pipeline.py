#!/usr/bin/env python

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from mashumaro import DataClassDictMixin

from pypeline.domain.execution_context import ExecutionContext as _ExecutionContext
from pypeline.domain.pipeline import PipelineConfig, PipelineLoader


@dataclass
class StepsConfig(DataClassDictMixin):
    #: Steps to execute
    my_steps: PipelineConfig

    @classmethod
    def from_file(cls, config_file: Path) -> "StepsConfig":
        config_dict = cls.parse_to_dict(config_file)
        return cls.from_dict(config_dict)

    @staticmethod
    def parse_to_dict(config_file: Path) -> dict[str, Any]:
        with open(config_file) as fs:
            return yaml.safe_load(fs)


@dataclass
class ExecutionContext(_ExecutionContext):
    def __init__(self, project_root_dir: Path) -> None:
        super().__init__(project_root_dir)
        self.result = 0


class MyStep(ABC):
    """Base class for my custom steps."""

    def __init__(
        self,
        execution_context: ExecutionContext,
        output_dir: Path,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.execution_context = execution_context
        self.config = config
        self.output_dir = output_dir

    @abstractmethod
    def calculate(self, input: int) -> int:
        pass


class MyStepReference:
    def __init__(self, group_name: Optional[str], _class: type[MyStep], config: Optional[dict[str, Any]] = None) -> None:
        self.group_name = group_name
        self._class = _class
        self.config = config

    @property
    def name(self) -> str:
        return self._class.__name__


class AddStep(MyStep):
    @property
    def param(self) -> int:
        return self.config["param"] if self.config and "param" in self.config else 0

    def calculate(self, input: int) -> int:
        print(f"  - Add {self.param} to {input}")
        self.execution_context.result = self.param + input
        return self.execution_context.result


class MultiplyStep(MyStep):
    @property
    def param(self) -> int:
        return self.config["param"] if self.config and "param" in self.config else 1

    def calculate(self, input: int) -> int:
        print(f"  - Multiply {input} by {self.param}")
        self.execution_context.result = self.param * input
        return self.execution_context.result


def main() -> None:
    project_root = Path(__file__).parent
    print("[1] Load and execute the steps from the 'steps.yaml' file")
    # Load the steps config file
    steps_config = StepsConfig.from_file(project_root / "steps.yaml")
    # Load the steps from the config file.
    # It will search for the steps classes either in the loaded modules or in the specified file
    steps_references = PipelineLoader[MyStep](steps_config.my_steps, project_root).load_steps_references()
    # Used to store the result of the pipeline and exchange data between steps
    execution_context = ExecutionContext(project_root)
    result = 0
    for step_reference in steps_references:
        # Instantiate the step
        step = step_reference._class(
            execution_context=execution_context,
            output_dir=project_root,
            config=step_reference.config,
        )
        # Run the step
        result = step.calculate(result)
    print("Result:", result)
    print("Execution context result:", execution_context.result)

    print("[2] Load and execute steps from list")
    my_step_references = [
        MyStepReference(None, AddStep, {"param": 10}),
        MyStepReference(None, MultiplyStep, {"param": 3}),
        MyStepReference(None, AddStep, {"param": 2}),
    ]
    execution_context = ExecutionContext(project_root)
    result = 0
    for my_step_ref in my_step_references:
        # Instantiate the step
        step = my_step_ref._class(
            execution_context=execution_context,
            output_dir=project_root,
            config=my_step_ref.config,
        )
        # Run the step
        result = step.calculate(result)
    print("Result:", result)
    print("Execution context result:", execution_context.result)


if __name__ == "__main__":
    main()
