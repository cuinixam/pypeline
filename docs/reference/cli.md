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
| `--command` | TEXT | — | Command appended as last step; pypeline waits for it |
| `--application` | TEXT | — | Application started detached once the pipeline finished |

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

## Running Commands and Applications

Both options use the environment collected by the pipeline: every `install_dirs` entry is in `PATH` and every `env_vars` entry is set. This is what makes them different from running the command yourself afterwards.

`--command` is appended to the schedule as a regular step. It runs last, pypeline waits for it and fails if it fails. Because it is a step, it is skipped by `--dry-run` and supports `${{ inputs.<name> }}` placeholders for the inputs declared in the configuration file.

```shell
pypeline run --step CreateVEnv --command "pytest -v"
pypeline run --command "ruff check ${{ inputs.target }}" -i target=src
```

`--application` adds no step. The pipeline runs, the application is started as a detached process and pypeline exits without waiting for it. Use it to launch editors, GUIs or shells that need the installed tools.

```shell
pypeline run --step ScoopInstall --application "code ."
pypeline run --application "cmd"
```
