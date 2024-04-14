# Pypeline

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

Pypeline is a Python application designed to streamline and automate the software development lifecycle, particularly the pipeline execution processes across various environments such as GitHub and Jenkins.
The primary motivation for developing Pypeline stemmed from the need to unify and simplify the creation of build, test, and deployment pipelines that are traditionally defined separately across these platforms using GitHub workflows (YAML) and Jenkins pipelines (Jenkinsfile).

**Key Features**

- **Unified Pipeline Definition**: Users can define their entire pipeline in a single YAML file, eliminating the need to switch between different syntaxes and configurations for different CI/CD tools.

- **Extensibility**: Pypeline supports execution steps defined not only through local scripts but also from installed Python packages.

- **Execution Context**: Each step in the pipeline receives an execution context that can be updated during step execution. This allows for the sharing of information and state between steps.

- **Dependency Handling**: Dependency management ensures that only the necessary steps are executed, reducing runtime and resource usage by avoiding unnecessary operations.

- **Ease of Use**: With Pypeline, setting up and running pipelines becomes more straightforward, enabling developers to focus more on coding and less on configuring pipeline specifics.

## Installation

Install this via pip (or your favourite package manager):

`pip install pypeline-runner`

## Start developing

The project uses Poetry for dependencies management and packaging.
Run the `bootstrap.ps1` script to install Python and create the virtual environment.

```powershell
.\bootstrap.ps1
```

This will also generate a `poetry.lock` file, you should track this file in version control.

To execute the test suite, call pytest inside Poetry's virtual environment via `poetry run`:

```shell
.venv/Scripts/poetry run pytest
```

Check out the Poetry documentation for more information on the available commands.

For those using [VS Code](https://code.visualstudio.com/) there are tasks defined for the most common commands:

- bootstrap
- install dependencies
- run tests
- run all checks configured for pre-commit
- generate documentation

See the `.vscode/tasks.json` for more details.

## Committing changes

This repository uses [commitlint](https://github.com/conventional-changelog/commitlint) for checking if the commit message meets the [conventional commit format](https://www.conventionalcommits.org/en).

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- prettier-ignore-start -->
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- markdownlint-disable -->
<!-- markdownlint-enable -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-end -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## Credits

This package was created with [Copier](https://copier.readthedocs.io/) and the [cuinixam/pypackage-template](https://github.com/cuinixam/pypackage-template) project template.
