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

## Built-in Steps

### CreateVEnv

Creates a Python virtual environment.

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `python_version` | string | — | Python version (e.g., `"3.13"`) |
| `python_executable` | string | — | Path to Python |
| `python_package_manager` | string | `uv>=0.6` | Package manager |
| `bootstrap_script` | string | — | Custom bootstrap script |

```yaml
- step: CreateVEnv
  module: pypeline.steps.create_venv
  config:
    python_version: "3.13"
    python_package_manager: uv>=0.6
```

### WestInstall

Downloads multi-repo dependencies using [west](https://docs.zephyrproject.org/latest/develop/west/).

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `manifest_file` | string | `west.yaml` | Relative path to west manifest file |
| `workspace_dir` | string | `build/` | Relative path for west workspace directory |

```yaml
- step: WestInstall
  module: pypeline.steps.west_install
  config:
    manifest_file: deps/west.yaml  # custom manifest location
    workspace_dir: external/deps   # custom workspace directory
```

The step supports multiple manifest sources. Beyond the configured manifest file, it collects every `WestManifestFile` registered in the execution context data registry by previous steps, and subclasses can override `_collect_manifests()` to contribute more sources. The collection order defines the override order, like git config files: the configured manifest is the base, and a later source's remote or project with the same name overrides the earlier definition. Every collected manifest file is tracked as a step input, so editing any of them re-runs the step.

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
