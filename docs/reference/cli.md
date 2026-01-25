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
