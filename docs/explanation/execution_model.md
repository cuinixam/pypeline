# Execution Model

How pypeline executes your pipeline steps.

## Execution Flow

```{mermaid}
sequenceDiagram
  participant CLI as pypeline run
  participant Slurp as ProjectSlurper
  participant Sched as PipelineScheduler
  participant Load as PipelineLoader
  participant Exec as PipelineStepsExecutor
  participant Step as PipelineStep

  CLI->>Slurp: Read pypeline.yaml
  Slurp-->>CLI: PipelineConfig
  CLI->>Sched: Filter steps (--step, --single)
  Sched-->>CLI: Step references
  CLI->>Load: Load step classes
  Load-->>CLI: Instantiated steps
  CLI->>Exec: Execute steps

  loop For each step
    Exec->>Step: Check dependencies
    alt Outdated or forced
      Exec->>Step: run()
    end
    Exec->>Step: update_execution_context()
  end
```

## ExecutionContext Lifecycle

The `ExecutionContext` flows through all steps:

1. **Created** by the CLI with project root and inputs
2. **Passed** to each step constructor
3. **Updated** by `update_execution_context()` after every step (even skipped ones)
4. **Used** by subsequent steps for shared state

### Key Properties

| Property | Purpose |
|----------|---------|
| `install_dirs` | PATH directories for subprocesses |
| `data_registry` | Type-safe key-value store |
| `inputs` | User-provided parameters |
| `env_vars` | Environment for subprocesses |

## Dependency Management

Steps declare inputs and outputs:

```python
def get_inputs(self) -> list[Path]:
  return [self.project_root_dir / "src"]

def get_outputs(self) -> list[Path]:
  return [self.output_dir / "build"]
```

The executor skips steps when:
- All outputs exist
- Outputs are newer than inputs
- `--force-run` is not set

## Subprocess Execution

Steps run external commands via `create_process_executor()`:

```python
executor = self.execution_context.create_process_executor(
  ["gcc", "-o", "main", "main.c"],
  cwd=self.project_root_dir
)
executor.execute()
```

The executor automatically:
- Adds `install_dirs` to PATH
- Injects `env_vars`
- Handles Windows/Unix shell differences
