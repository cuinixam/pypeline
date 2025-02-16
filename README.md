<p align="center">
<a href="https://pypeline-runner.readthedocs.io">
<img align="center" src="https://github.com/cuinixam/pypeline/raw/main/logo.png" width="400"/>
</a>
</p>

# pypeline - Define Your CI/CD Pipeline Once, Run It Anywhere

<p align="center">
  <a href="https://github.com/cuinixam/pypeline/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/cuinixam/pypeline/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://pypeline-runner.readthedocs.io">
    <img src="https://img.shields.io/readthedocs/pypeline-runner.svg?logo=read-the-docs&logoColor=fff&style=flat-square" alt="Documentation Status">
  </a>
  <a href="https://codecov.io/gh/cuinixam/pypeline">
    <img src="https://img.shields.io/codecov/c/github/cuinixam/pypeline.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://python-poetry.org/">
    <img src="https://img.shields.io/badge/packaging-poetry-299bd7?style=flat-square&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAASCAYAAABrXO8xAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAJJSURBVHgBfZLPa1NBEMe/s7tNXoxW1KJQKaUHkXhQvHgW6UHQQ09CBS/6V3hKc/AP8CqCrUcpmop3Cx48eDB4yEECjVQrlZb80CRN8t6OM/teagVxYZi38+Yz853dJbzoMV3MM8cJUcLMSUKIE8AzQ2PieZzFxEJOHMOgMQQ+dUgSAckNXhapU/NMhDSWLs1B24A8sO1xrN4NECkcAC9ASkiIJc6k5TRiUDPhnyMMdhKc+Zx19l6SgyeW76BEONY9exVQMzKExGKwwPsCzza7KGSSWRWEQhyEaDXp6ZHEr416ygbiKYOd7TEWvvcQIeusHYMJGhTwF9y7sGnSwaWyFAiyoxzqW0PM/RjghPxF2pWReAowTEXnDh0xgcLs8l2YQmOrj3N7ByiqEoH0cARs4u78WgAVkoEDIDoOi3AkcLOHU60RIg5wC4ZuTC7FaHKQm8Hq1fQuSOBvX/sodmNJSB5geaF5CPIkUeecdMxieoRO5jz9bheL6/tXjrwCyX/UYBUcjCaWHljx1xiX6z9xEjkYAzbGVnB8pvLmyXm9ep+W8CmsSHQQY77Zx1zboxAV0w7ybMhQmfqdmmw3nEp1I0Z+FGO6M8LZdoyZnuzzBdjISicKRnpxzI9fPb+0oYXsNdyi+d3h9bm9MWYHFtPeIZfLwzmFDKy1ai3p+PDls1Llz4yyFpferxjnyjJDSEy9CaCx5m2cJPerq6Xm34eTrZt3PqxYO1XOwDYZrFlH1fWnpU38Y9HRze3lj0vOujZcXKuuXm3jP+s3KbZVra7y2EAAAAAASUVORK5CYII=" alt="Poetry">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="ruff">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/pypeline-runner/">
    <img src="https://img.shields.io/pypi/v/pypeline-runner.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/pypeline-runner.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/pypeline-runner.svg?style=flat-square" alt="License">
</p>

Pypeline lets you define your build, test, and deployment pipeline in a single YAML file and run it _consistently_ across your local development environment and _any_ CI/CD platform (GitHub Actions, Jenkins, etc.). No more platform-specific configurations – write once, run anywhere.

**Key Features**

- **Unified Pipeline Definition**: Users can define their entire pipeline in a single YAML file, eliminating the need to switch between different syntaxes and configurations for different CI/CD tools.

- **Extensibility**: Pypeline supports execution steps defined not only through installed Python packages but also from local scripts.

- **Execution Context**: Allow sharing information and state between steps. Each step in the pipeline receives an execution context that can be updated during step execution.

- **Dependency Handling**: Every step can register its dependencies and will only be scheduled if anything has changed.

## Installation

Use pipx (or your favorite package manager) to install and run it in an isolated environment:

```shell
pipx install pypeline-runner
```

This will install the `pypeline` command globally, which you can use to run your pipelines.

> [!NOTE]
> The Python package is called `pypeline-runner` because the name `pypeline` was already taken on PyPI.
> The command-line interface is `pypeline`.

Documentation: [pypeline-runner.readthedocs.io](https://pypeline-runner.readthedocs.io)

## Walkthrough: Getting Started with Pypeline

To get started run the `init` command to create a sample project:

```shell
pypeline init --project-dir my-pipeline
```

The example project pipeline is defined in the `pipeline.yaml` file.

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

This pipeline consists of three steps:

- `CreateVEnv`: This is a built-in step that creates a Python virtual environment.
- `WestInstall`: This is a built-in step that downloads external modules using the `west` tool.
- `MyStep`: This is a custom step that runs a script defined in the `steps/my_step.py` file.

You can run the pipeline using the `run` command:

```shell
pypeline run --project-dir my-pipeline
```

## Contributing

The project uses Poetry for dependencies management and packaging.
Run the `bootstrap.ps1` script to install Python and create the virtual environment.

```powershell
.\bootstrap.ps1
```

To execute the test suite, call pytest inside Poetry's virtual environment via `poetry run`:

```shell
.venv/Scripts/poetry run pytest
```

For those using [VS Code](https://code.visualstudio.com/) there are tasks defined for the most common commands:

- run tests
- run all checks configured for pre-commit
- generate documentation

See the `.vscode/tasks.json` for more details.

This repository uses [commitlint](https://github.com/conventional-changelog/commitlint) for checking if the commit message meets the [conventional commit format](https://www.conventionalcommits.org/en).

## Credits

This package was created with [Copier](https://copier.readthedocs.io/) and the [cuinixam/pypackage-template](https://github.com/cuinixam/pypackage-template) project template.
