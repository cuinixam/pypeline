# Hello Pypeline!

This guide will walk you through the process of installing Pypeline and kick-starting your first project.

## Installation

Use pipx (or your favorite package manager) to install and run it in an isolated environment:

```shell
pipx install pypeline-runner
```

This will install the `pypeline` command globally, which you can use to run your pipelines.

```{note}
The Python package is called `pypeline-runner` because the name `pypeline` was already taken on PyPI.
The command-line interface is `pypeline`.
```

Documentation: [pypeline-runner.readthedocs.io](https://pypeline-runner.readthedocs.io)

## Kickstart

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
