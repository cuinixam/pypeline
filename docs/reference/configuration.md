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

```yaml
- step: WestInstall
  module: pypeline.steps.west_install
```

### ScoopInstall

Installs Windows applications via [Scoop](https://scoop.sh/).

```yaml
- step: ScoopInstall
  module: pypeline.steps.scoop_install
```

```{warning}
Windows only. Logs a warning and skips on other platforms.
```

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
