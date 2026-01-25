# Creating Custom Steps

Learn how to create custom pipeline steps for your specific build, test, or deployment needs.

## Step Basics

Every step inherits from `PipelineStep[ExecutionContext]` and implements:

- `run()` – Execute the step's logic
- `update_execution_context()` – Share state with subsequent steps

## Minimal Example

Create `steps/hello_step.py`:

```python
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep


class HelloStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    print("Hello from my custom step!")

  def update_execution_context(self) -> None:
    pass  # No state to share
```

Reference it in `pypeline.yaml`:

```yaml
pipeline:
  - step: HelloStep
    file: steps/hello_step.py
```

## Using Configuration

Steps can receive configuration from the YAML:

```python
class ConfigurableStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    message = self.config.get("message", "default")
    count = self.config.get("count", 1)
    for _ in range(count):
      print(message)

  def update_execution_context(self) -> None:
    pass
```

```yaml
pipeline:
  - step: ConfigurableStep
    file: steps/my_step.py
    config:
      message: "Build started!"
      count: 3
```

## Sharing State Between Steps

Use `ExecutionContext` to pass data downstream:

```python
class SetupStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    # Install tools to a directory
    self.tool_dir = self.output_dir / "tools"
    self.tool_dir.mkdir(exist_ok=True)

  def update_execution_context(self) -> None:
    # Add tool directory to PATH for subsequent steps
    self.execution_context.add_install_dirs([self.tool_dir])
```

Access shared data in later steps:

```python
class BuildStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    # Tools from SetupStep are now in PATH
    executor = self.execution_context.create_process_executor(
      ["my-tool", "--version"]
    )
    executor.execute()

  def update_execution_context(self) -> None:
    pass
```

## Dependency Management

Implement `get_inputs()` and `get_outputs()` for smart rebuilds:

```python
class CompileStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    # Compile source files
    pass

  def get_inputs(self) -> list[Path]:
    return list(self.project_root_dir.glob("src/**/*.c"))

  def get_outputs(self) -> list[Path]:
    return [self.output_dir / "output.bin"]

  def update_execution_context(self) -> None:
    pass
```

The step only runs when inputs are newer than outputs.

## Next Steps

- [Architecture Overview](../explanation/architecture.md) – Understand the execution model
- [API Reference](../reference/api/index.md) – Full class documentation
