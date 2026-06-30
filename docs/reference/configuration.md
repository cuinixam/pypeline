# Configuration Reference

Complete schema for `pypeline.yaml`.

## Top-Level Structure

```yaml
inputs:
  <input_name>:
    type: <type>
    description: <text>
    default: <value>

pipeline:
  # List of steps (flat)
  - step: StepName
    ...

  # OR grouped steps
  group_name:
    - step: StepName
      ...
```

```{note}
A malformed `pypeline.yaml` (a wrong type or a missing required field) is reported with its exact `file:line:column`, pointing at the offending step or input instead of the top of the file, so you can jump straight to it.
```

## Step Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step` | string | ✓ | Step class name |
| `module` | string | | Python module path |
| `file` | string | | Local `.py` file path |
| `run` | string/list | | Shell command |
| `class_name` | string | | Override class name |
| `description` | string | | Step description |
| `timeout_sec` | integer | | Timeout in seconds |
| `config` | object | | Step-specific config |

```{note}
One of `module`, `file`, or `run` is required.
```

## Step Types

### Module Step

```yaml
- step: CreateVEnv
  module: pypeline.steps.create_venv
  config:
    python_version: "3.13"
```

### File Step

```yaml
- step: MyStep
  file: steps/my_step.py
  config:
    param: value
```

### Command Step

```yaml
- step: Lint
  run: ruff check .

# Or as list
- step: Test
  run: [pytest, -v, --cov]

# Multiple commands (GitHub Actions style)
- step: QualityChecks
  run: |
    ruff check .
    pytest -v --cov
```

---

## Including Other Pipeline Files

A `pipeline` entry can pull in the steps of another pypeline file with `include:` instead of `step:`. The included steps are spliced in **at that position**, so where the `include` sits is where its steps run:

```yaml
# pypeline.yaml
pipeline:
  - include: bootstrap.pypeline.yaml   # its steps run here, before the rest
  - step: Build
    run: cmake --build build
```

```yaml
# bootstrap.pypeline.yaml — a valid pypeline file on its own
pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
  - step: InstallDeps
    run: uv sync
```

### Including only selected steps

An included file often defines more steps than any single pipeline needs. A `bootstrap.pypeline.yaml` might set up the whole environment (create the virtual environment, install dependencies, generate a setup script), but one pipeline only wants the venv and the setup script. Instead of copying those steps or including the whole file, name the ones you want under `steps:`. Only those are included; the rest of the file is ignored:

```yaml
# pypeline.yaml
pipeline:
  - include:
      file: bootstrap.pypeline.yaml
      steps: [CreateVEnv, GenerateSetupScript]
  - step: Build
    run: cmake --build build
```

- **Selected steps keep the included file's defined order**, not the order you list them in `steps:`.
- **An unknown step name is an error**, so a typo or a renamed step fails fast instead of being silently skipped.
- Omitting `steps:` (or using the plain string form `include: bootstrap.pypeline.yaml`) includes the whole file.

### Include instead of repeating a step

You could copy a step's config into the new file instead of including it, but that has two costs:

- **Duplicated config.** The same step now lives in two places and has to be kept in sync.
- **A different output location.** A step's output directory (and the `.deps.json` dependency record in it) is keyed to the file where the step is *defined*. Re-declaring the step in another file, especially under a group, gives it a different location, so its incremental cache no longer matches the original and the step re-runs.

Including the step keeps one copy of the config and guarantees the same output location, so the cached result is reused (see the note on output directories below).

### Notes

- **Path** is resolved relative to the **including** file. Includes may be nested (an included file may include another); a cycle is reported as an error.
- **The included file must define a flat list** of steps (no groups).
- **An included file runs both ways.** `bootstrap.pypeline.yaml` is a normal pypeline file, so you can run it on its own (`pypeline run --config-file bootstrap.pypeline.yaml`) *and* include it.

```{important}
A step's output directory is determined by the file where the step is **defined**, never by the file that includes it. So a step produces the same outputs — and reuses the same incremental cache — whether you run its file standalone or as part of a larger pipeline. Splicing an include into a group changes execution order only, not where the included steps write.
```

```{note}
Includes do not defer step-class resolution: an included file that *installs* the package providing a **later** step cannot bootstrap that step in the same run (the later step's class must already be importable). Use `include:` to organise and reuse steps whose classes are already available.
```

---

## Built-in Steps

### CreateVEnv

Creates a Python virtual environment.

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `python_version` | string | — | Python version (e.g., `"3.13"`) — **preferred** |
| `python_executable` | string | — | Path to Python (legacy; prefer `python_version`) |
| `python_package_manager` | string | `uv>=0.6` | Package manager |
| `bootstrap_script` | string | — | Custom bootstrap script |

```yaml
- step: CreateVEnv
  module: pypeline.steps.create_venv
  config:
    python_version: "3.13"
    python_package_manager: uv>=0.6
```

```{note}
Prefer `python_version` over `python_executable`. The bootstrap environment is cached per Python `major.minor`; pinning `python_version` keeps that identity stable, while relying on a bare `python_executable` (e.g. `python3`) lets it drift with `PATH` between steps and rebuild needlessly. New projects from `pypeline init` pin `python_version` to the interpreter that created them.
```

### WestInstall

Downloads multi-repo dependencies using [west](https://docs.zephyrproject.org/latest/develop/west/).

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `manifest_file` | string | `west.yaml` | Relative path to west manifest file |
| `workspace_dir` | string | `build/` | Relative path for west workspace directory |
| `revision_scoped_paths` | bool | `false` | Nest each dependency under a revision subdirectory |

```yaml
- step: WestInstall
  module: pypeline.steps.west_install
  config:
    manifest_file: deps/west.yaml  # custom manifest location
    workspace_dir: external/deps   # custom workspace directory
    revision_scoped_paths: true          # external/zephyr/v3.2.0 instead of external/zephyr
```

A project can select different west manifests for different configurations, and two configurations may pin the same dependency at different revisions. Because the install workspace is shared, that dependency otherwise resolves to one install path and west re-checks-out that directory each time a configuration with a different pin is built. Setting `revision_scoped_paths: true` appends each dependency's revision to its `path` (`external/zephyr` at `v3.2.0` becomes `external/zephyr/v3.2.0`), so the revisions live side by side. The flag defaults to `false` to keep the flat layout; toggling it re-runs the step.

The step supports multiple manifest sources. Beyond the configured manifest file, it collects every `WestManifestFile` registered in the execution context data registry by previous steps, and subclasses can override `_collect_manifests()` to contribute more sources. The collection order defines the override order, like git config files: the configured manifest is the base, and a later source's remote or project with the same name overrides the earlier definition. Every collected manifest file is tracked as a step input, so editing any of them re-runs the step.

After installing, the step publishes one `ExternalProject` (`pypeline.domain.external_project`) per project to the data registry, each carrying the project `name`, its `revision`, and the resolved absolute install `path`. A later step finds a dependency by name instead of hardcoding where it lives:

```python
from pypeline.domain.external_project import ExternalProject

zephyr = next(p for p in self.execution_context.data_registry.find_data(ExternalProject) if p.name == "zephyr")
configure_cmd = ["cmake", f"-DZEPHYR_BASE={zephyr.path}"]
```

This is what makes `revision_scoped_paths` safe to turn on: the install layout is an internal detail, and consumers always get the actual location. The projects are published whether west ran or was skipped on a cache hit.

Because `west.yaml` is YAML, a malformed entry (a wrong type or a missing required field) is reported with its exact `file:line:column`, so you can jump straight to the offending line instead of hunting for it. The generated manifest carries only the merged values; the source locations are dropped on the way out.

### ScoopInstall

Installs Windows applications via [Scoop](https://scoop.sh/).

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| — | — | — | No configuration options |

```yaml
- step: ScoopInstall
  module: pypeline.steps.scoop_install
```

Dependencies are read from `scoopfile.json` in the project root. Like `WestInstall`, the step supports multiple manifest sources: it collects every `ScoopManifestFile` registered in the data registry, and subclasses can override `_collect_manifests()` to contribute more. The collection order defines the override order, like git config files: the root `scoopfile.json` is the base, and a later source's bucket or app with the same name overrides the earlier definition. Every collected manifest file is tracked as a step input.

```{warning}
Windows only. Logs a warning and skips on other platforms.
```

### PoksInstall

Installs tools cross-platform via [poks](https://github.com/cuinixam/poks) (a scoop-like package manager that works on Windows, Linux, and macOS).

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `install_dir` | string | `~/.poks` | Relative path from project root for the poks installation directory (`.poks` is appended) |

```yaml
- step: PoksInstall
  module: pypeline.steps.poks_install
  config:
    install_dir: build/tools
```

Dependencies are read from `poks.json` in the project root. The step supports multiple config sources: it collects every `PoksManifestFile` registered in the data registry, and subclasses can override `_collect_manifests()` to contribute more. The collection order defines the override order, like git config files: the root `poks.json` is the base, and a later source's bucket or app with the same name overrides the earlier definition. Every collected config file is tracked as a step input.

### GenerateEnvSetupScript

Generates environment setup scripts for shell sessions.

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| — | — | — | No configuration options |

```yaml
- step: GenerateEnvSetupScript
  module: pypeline.steps.env_setup_script
```

Generates platform-specific scripts:
- `build/env_setup.sh` (Unix/Linux/macOS)
- `build/env_setup.ps1` (Windows PowerShell)
- `build/env_setup.bat` (Windows CMD)

Use before opening an IDE to set up PATH and environment variables:

```shell
source ./build/env_setup.sh
```

---

## Groups (Optional)

Group related steps together:

```yaml
pipeline:
  venv:
    - step: CreateVEnv
      module: pypeline.steps.create_venv

  build:
    - step: Compile
      file: steps/compile.py
    - step: Link
      file: steps/link.py

  test:
    - step: UnitTest
      run: pytest
```

Each group creates a subdirectory in `build/` for outputs.
