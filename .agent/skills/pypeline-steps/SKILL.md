---
name: pypeline-steps
description: Create and run custom pipeline steps using the pypeline framework. Use when creating new PipelineStep classes, accessing ExecutionContext (inputs, data_registry, env_vars), or configuring steps in pypeline.yaml. Covers step configuration, data registry patterns, subprocess execution, and running pipelines.
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
