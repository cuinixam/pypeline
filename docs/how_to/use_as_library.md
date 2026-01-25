# Use Pypeline as a Library

Load and execute pipeline steps programmatically in your Python code.

## Overview

You can use pypeline's core classes to:
- Load step definitions from YAML or Python lists
- Execute steps with a custom `ExecutionContext`
- Share data between steps via the context

## Complete Example

This example shows two approaches: loading from YAML and from a Python list.

### Define Custom Steps

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pypeline.domain.execution_context import (
  ExecutionContext as _ExecutionContext,
)


@dataclass
class ExecutionContext(_ExecutionContext):
  """Extended context with custom result storage."""
  def __init__(self, project_root_dir: Path) -> None:
    super().__init__(project_root_dir)
    self.result = 0


class MyStep(ABC):
  """Base class for custom steps."""
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


class AddStep(MyStep):
  @property
  def param(self) -> int:
    return self.config.get("param", 0) if self.config else 0

  def calculate(self, input: int) -> int:
    self.execution_context.result = self.param + input
    return self.execution_context.result


class MultiplyStep(MyStep):
  @property
  def param(self) -> int:
    return self.config.get("param", 1) if self.config else 1

  def calculate(self, input: int) -> int:
    self.execution_context.result = self.param * input
    return self.execution_context.result
```

### Load Steps from YAML

Create `steps.yaml`:

```yaml
my_steps:
  - step: AddStep
    file: custom_pipeline.py
    config:
      param: 5
  - step: MultiplyStep
    file: custom_pipeline.py
    config:
      param: 2
```

Load and execute:

```python
import yaml
from dataclasses import dataclass
from pathlib import Path
from mashumaro import DataClassDictMixin
from pypeline.domain.pipeline import (
  PipelineConfig,
  PipelineLoader,
)


@dataclass
class StepsConfig(DataClassDictMixin):
  my_steps: PipelineConfig

  @classmethod
  def from_file(cls, config_file: Path) -> "StepsConfig":
    with open(config_file) as fs:
      return cls.from_dict(yaml.safe_load(fs))


def main() -> None:
  project_root = Path(__file__).parent

  # Load steps from YAML
  steps_config = StepsConfig.from_file(
    project_root / "steps.yaml"
  )

  # Load step classes
  step_refs = PipelineLoader(
    steps_config.my_steps,
    project_root
  ).load_steps_references()

  # Execute steps
  context = ExecutionContext(project_root)
  result = 0
  for ref in step_refs:
    step = ref._class(
      execution_context=context,
      output_dir=project_root,
      config=ref.config,
    )
    result = step.calculate(result)

  print(f"Result: {result}")  # Output: 12
```

### Load Steps Programmatically

```python
class MyStepReference:
  def __init__(
    self,
    group_name: Optional[str],
    _class: type[MyStep],
    config: Optional[dict[str, Any]] = None,
  ) -> None:
    self.group_name = group_name
    self._class = _class
    self.config = config


def run_programmatic() -> None:
  project_root = Path.cwd()

  # Define steps in code
  step_refs = [
    MyStepReference(None, AddStep, {"param": 10}),
    MyStepReference(None, MultiplyStep, {"param": 3}),
    MyStepReference(None, AddStep, {"param": 2}),
  ]

  # Execute
  context = ExecutionContext(project_root)
  result = 0
  for ref in step_refs:
    step = ref._class(
      execution_context=context,
      output_dir=project_root,
      config=ref.config,
    )
    result = step.calculate(result)

  print(f"Result: {result}")  # Output: 32
```

## Key Classes

| Class | Purpose |
|-------|---------|
| `PipelineLoader` | Loads step classes from config |
| `ExecutionContext` | Shared state container |
| `PipelineStepReference` | Holds step class and config |

See [examples/custom_pipeline.py](https://github.com/cuinixam/pypeline/blob/main/examples/custom_pipeline.py) for the complete working example.
