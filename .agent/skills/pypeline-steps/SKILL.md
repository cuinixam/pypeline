---
name: pypeline-steps
description: Create and run custom pipeline steps using the pypeline framework. Use when creating new PipelineStep classes, accessing ExecutionContext (inputs, data_registry, env_vars), or configuring steps in pypeline.yaml. Also use when a user wants to model any sequence of operations as a custom pipeline — PipelineLoader and PipelineConfig are generic (PipelineLoader[T]) so users can define their own step base class, implement concrete steps, and run them with the pipeline machinery (shared context, dependency tracking, YAML config). Covers step configuration, data registry patterns, subprocess execution, custom pipelines, and running pipelines.
---

# Pypeline Steps

Create custom pipeline steps for the pypeline framework.

## Creating a Step

```python
from pathlib import Path
from typing import List

from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


class MyStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        # Main step logic
        logger.info(f"Running {self.get_name()}")

    def get_inputs(self) -> List[Path]:
        # File dependencies - step skipped if unchanged
        return []

    def get_outputs(self) -> List[Path]:
        # Output files for dependency tracking
        return []

    def get_name(self) -> str:
        return self.__class__.__name__

    def update_execution_context(self) -> None:
        # Called ALWAYS (even if step skipped) to share state with subsequent steps
        pass
```

## Step Configuration

Define custom config using `mashumaro` dataclass:

```python
from dataclasses import dataclass
from typing import Optional
from mashumaro.mixins.json import DataClassJSONMixin

@dataclass
class MyStepConfig(DataClassJSONMixin):
    timeout: int = 30
    output_dir: Optional[str] = None


class MyStep(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config=None):
        self.user_config = MyStepConfig.from_dict(config) if config else MyStepConfig()
        super().__init__(execution_context, group_name, config)
```

## ExecutionContext Access

```python
def run(self) -> None:
    # Get user inputs from CLI (-i key=value)
    value = self.execution_context.get_input("my_param")

    # Project paths
    root = self.execution_context.project_root_dir
    artifacts = self.execution_context.create_artifacts_locator()
    build_dir = artifacts.build_dir  # build/

    # Execute subprocesses (auto-inherits install_dirs in PATH, env_vars)
    executor = self.execution_context.create_process_executor(["my-tool", "arg"])
    executor.execute()
```

## DataRegistry

Type-based storage for exchanging arbitrary data between steps:

```python
from dataclasses import dataclass

@dataclass
class BuildInfo:
    version: str
    artifact_path: Path

# Insert data (in one step)
def update_execution_context(self) -> None:
    info = BuildInfo(version="1.0.0", artifact_path=self.output_dir / "app.zip")
    self.execution_context.data_registry.insert(info, provider=self.get_name())

# Retrieve data (in another step)
def run(self) -> None:
    # Find all BuildInfo entries
    entries = self.execution_context.data_registry.find_data(BuildInfo)
    if entries:
        info = entries[0]  # Get first match
        logger.info(f"Build version: {info.version}")

    # Find with provider info
    data_entries = self.execution_context.data_registry.find_entries(BuildInfo)
    for entry in data_entries:
        logger.info(f"From {entry.provider}: {entry.data}")
```

## Sharing State

```python
def update_execution_context(self) -> None:
    # Add directories to subprocess PATH for subsequent steps
    self.execution_context.add_install_dirs([self.output_dir / "bin"])

    # Add environment variables for subprocesses
    self.execution_context.add_env_vars({"MY_VAR": "value"})
```

## pypeline.yaml Configuration

### Load from file (project-local)
```yaml
pipeline:
  - step: MyStep
    file: steps/my_step.py
    config:
      timeout: 60
      output_dir: build/output
```

### Load from module (installed package)
```yaml
pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      python_package_manager: uv>=0.6
```

### Simple command (no class needed)
```yaml
pipeline:
  - step: RunTests
    run: pytest -v tests/
```

### With inputs
```yaml
inputs:
  environment:
    type: string
    description: Target environment
    default: development

pipeline:
  - step: Deploy
    file: steps/deploy.py
```

## Running Pipelines

```bash
# Run full pipeline
pypeline run

# Run steps up to and including MyStep
pypeline run --step MyStep

# Run only MyStep
pypeline run --step MyStep --single

# Pass inputs
pypeline run -i environment=production -i debug=true
```

## Force Step Execution

Override dependency checking to always run:

```python
def get_needs_dependency_management(self) -> bool:
    return False  # Step always runs
```

## Custom Pipelines

`PipelineConfig` and `PipelineLoader[T]` are generic — they don't require `PipelineStep`. This means you can model **any sequence of operations** as a custom pipeline with your own step base class, getting shared execution context, YAML-driven configuration, and step dependency tracking without coupling to pypeline's built-in steps.

### Pattern

1. Define your own step base class and execution context
2. Implement concrete step classes
3. Use `PipelineLoader[YourBase]` to load steps from YAML (or construct them programmatically)
4. Instantiate and run each step yourself

### Example

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from mashumaro import DataClassDictMixin
from pypeline.domain.execution_context import ExecutionContext as _ExecutionContext
from pypeline.domain.pipeline import PipelineConfig, PipelineLoader


# Extend ExecutionContext to carry custom shared state
class ExecutionContext(_ExecutionContext):
    def __init__(self, project_root_dir: Path) -> None:
        super().__init__(project_root_dir)
        self.result = 0  # shared state between steps


# Your own step base class — no dependency on PipelineStep
class MyStep(ABC):
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


# Concrete step implementations
class AddStep(MyStep):
    def calculate(self, input: int) -> int:
        param = self.config.get("param", 0) if self.config else 0
        self.execution_context.result = param + input
        return self.execution_context.result


class MultiplyStep(MyStep):
    def calculate(self, input: int) -> int:
        param = self.config.get("param", 1) if self.config else 1
        self.execution_context.result = param * input
        return self.execution_context.result
```

### Loading from a Config File

`PipelineConfig` just needs a dict — the config file format (YAML, JSON, TOML, etc.) is up to you. `StepsConfig` is responsible for parsing the file into a dict.

**Example config (`steps.yaml`):**
```yaml
my_steps:
  - step: AddStep
    file: my_steps.py
    config:
      param: 5
  - step: MultiplyStep
    file: my_steps.py
    config:
      param: 3
```

**Same structure as JSON (`steps.json`):**
```json
{
  "my_steps": [
    {"step": "AddStep", "file": "my_steps.py", "config": {"param": 5}},
    {"step": "MultiplyStep", "file": "my_steps.py", "config": {"param": 3}}
  ]
}
```

```python
import json
import yaml

@dataclass
class StepsConfig(DataClassDictMixin):
    my_steps: PipelineConfig

    @classmethod
    def from_yaml(cls, path: Path) -> "StepsConfig":
        return cls.from_dict(yaml.safe_load(path.read_text()))

    @classmethod
    def from_json(cls, path: Path) -> "StepsConfig":
        return cls.from_dict(json.loads(path.read_text()))

# PipelineLoader[MyStep] — T is your base class
steps_config = StepsConfig.from_yaml(Path("steps.yaml"))
step_refs = PipelineLoader[MyStep](steps_config.my_steps, project_root).load_steps_references()

execution_context = ExecutionContext(project_root)
result = 0
for ref in step_refs:
    step = ref._class(execution_context=execution_context, output_dir=project_root, config=ref.config)
    result = step.calculate(result)
```

### Constructing Steps Programmatically

Steps don't have to come from YAML — construct references directly:

```python
my_steps = [
    (AddStep, {"param": 10}),
    (MultiplyStep, {"param": 3}),
    (AddStep, {"param": 2}),
]

result = 0
for step_class, config in my_steps:
    step = step_class(execution_context=execution_context, output_dir=project_root, config=config)
    result = step.calculate(result)
```
