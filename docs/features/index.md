# ✨ Features

## Unified Pipeline Definition

Users can define their entire pipeline in a single YAML file, eliminating the need to switch between different syntaxes and configurations for different CI/CD tools.

```{code-block} yaml
:caption: Example pypeline.yaml
pipeline:
  venv:
    - step: CreateVEnv
      module: pypeline.steps.create_venv
      config:
        bootstrap_script: .bootstrap/bootstrap.py
  install:
    - step: ScoopInstall
      module: pypeline.steps.scoop_install
  build:
    - step: MyBuildStep
      file: steps/build_step.py
```

### Steps

These are the building blocks of the pipeline. Each step is a Python class that defines a single task in the pipeline.

- `step` - Step class name (alias for `class_name`)
- `module` - Python module with step class
- `file` - Path to file with step class. The path should be relative to the project root directory.
- `class_name` - Step class name
- `config` - The user can provide configuration options for each step. See the step specific documentation for available options.

### Groups

In the `pypeline.yaml`, each top-level key under `pipeline` represents a `group` in the pipeline.
These are only used to cluster together steps that are logically related.
For every group, a new directory is created (in the build directory) where all the steps in the group shall create their outputs.

_Why use groups?_
To logically group steps together. For example, all steps related to code generation can be grouped under the `gen` group. This makes it easier to search for generated files and outputs.

:::{note}
The name of the group shall be unique and a valid directory name. For every group a directory is created in the build directory.
:::

## Create Virtual Environment

Create a virtual environment for the project using the [bootstrap](https://github.com/avengineers/bootstrap) module.

## Install Scoop Applications

Install applications using a [wrapper](https://python-app-dev.readthedocs.io/en/latest/features/scoop_wrapper.html) for the Scoop package manager for Windows.
