# Your First Pipeline

This tutorial walks you through installing Pypeline and running your first pipeline in under 5 minutes.

## Prerequisites

- Python 3.10 or higher
- [pipx](https://pipx.pypa.io/) (recommended) or pip

## Installation

Install Pypeline using pipx:

```shell
pipx install pypeline-runner
```

```{note}
The package is `pypeline-runner` on PyPI, but the CLI command is `pypeline`.
```

## Create a Sample Project

Bootstrap a new project with the `init` command:

```shell
pypeline init --project-dir my-pipeline
cd my-pipeline
```

This creates a project with:

```
my-pipeline/
├── pypeline.yaml          # Pipeline definition
├── west.yaml              # (Optional) Multi-repo manifest
├── steps/
│   └── my_step.py         # Custom step example
└── .bootstrap/
    └── bootstrap.py       # Python environment setup
```

## Understanding the Pipeline

Open `pypeline.yaml` to see the pipeline definition:

```yaml
pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      bootstrap_script: .bootstrap/bootstrap.py
  - step: WestInstall
    module: pypeline.steps.west_install
    description: Download external modules
  - step: MyStep
    file: steps/my_step.py
    description: Run a custom script
```

Each step can be:
- **Module-based**: A class from an installed Python package
- **File-based**: A class from a local `.py` file
- **Command-based**: A shell command via `run:`

## Run the Pipeline

Execute all steps:

```shell
pypeline run
```

Run up to a specific step:

```shell
pypeline run --step MyStep
```

Run only a single step:

```shell
pypeline run --step CreateVEnv --single
```

## Next Steps

- [Creating Custom Steps](creating_custom_steps.md) – Build your own pipeline steps
- [Configuration Reference](../reference/configuration.md) – Full YAML schema
