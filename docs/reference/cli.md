# CLI Reference

Command-line interface for pypeline.

## Commands

### `pypeline init`

Create a new pypeline project.

```shell
pypeline init [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--project-dir` | PATH | Current directory | Target directory |
| `--force` | FLAG | `false` | Overwrite existing files |

### `pypeline run`

Execute the pipeline.

```shell
pypeline run [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--project-dir` | PATH | Current directory | Project root |
| `--config-file` | TEXT | `pypeline.yaml` | Pipeline config file |
| `--step` | TEXT | (all) | Step name(s) to run |
| `--single` | FLAG | `false` | Run only named step, skip predecessors |
| `--print` | FLAG | `false` | Print steps without executing |
| `--force-run` | FLAG | `false` | Force execution ignoring dependencies |
| `--dry-run` | FLAG | `false` | Show what would run |
| `-i`, `--input` | TEXT | — | Input as `key=value` (repeatable) |
| `--command` | TEXT | — | Command to append and execute as a final step after the scheduled pipeline steps |
| `--command-detach` | FLAG | `false` | Start the command as a detached process and exit immediately without waiting |

### `pypeline --version`

Show version and exit.

```shell
pypeline --version
```

## Examples

```shell
# Run entire pipeline
pypeline run

# Run up to BuildStep
pypeline run --step BuildStep

# Run only TestStep
pypeline run --step TestStep --single

# Pass inputs
pypeline run -i env=prod -i debug=true

# Preview without running
pypeline run --print
```

## Running Ad-hoc Commands

After pipeline steps install tools and configure environment variables, you may want to launch a process (like VS Code or a terminal) that inherits all those paths and variables. The `--command` option appends an arbitrary shell command as the final step after the scheduled pipeline steps.

### Examples

**Run a command and wait for it to finish (default):**

```shell
pypeline run --step CreateVEnv --single --command "python --version"
```

**Open VS Code as a detached process (exits immediately):**

```shell
pypeline run --step ScoopInstall --command "code ." --command-detach
```

**Run the full pipeline, then open a terminal with all paths and env vars:**

```shell
pypeline run --command "cmd" --command-detach
```

### How It Works

1. Pypeline schedules and executes the pipeline steps as usual (filtered by `--step`/`--single` or all steps).
2. Each step's `update_execution_context()` is called, propagating `install_dirs` and `env_vars`.
3. After all scheduled steps complete, the command is executed using the accumulated `ExecutionContext` (all installed tool paths in `PATH` and environment variables).
4. By default, pypeline waits for the command to finish. With `--command-detach`, the process is started in the background and pypeline exits immediately — useful for launching GUI applications like VS Code.
