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
    - step: print_env
      description: print the env
      run: set
  build:
    - step: MyBuildStep
      file: steps/build_step.py
```

### Steps

These are the building blocks of the pipeline. Each step is a Python class that defines a single task in the pipeline.

- `step` - Step class name (alias for `class_name`)
- `module` - Python module with step class
- `file` - Path to file with step class. The path should be relative to the project root directory.
- `run` - Command to run. For simple steps that don't need a class
- `class_name` - Step class name
- `config` - The user can provide configuration options for each step. See the step specific documentation for available options.

### Step Types

Steps can be either Python classes or simple commands. The user can choose the appropriate method based on the complexity of the task.

For complex tasks that require dependency management or must provide user configuration options, one shall create steps as Python classes.
These classes should inherit from the `PipelineStep` class. One can either refer to a class in a Python module or provide the class definition in a file.

Examples:

```{code-block} yaml
:caption: Example step from a Python module
pipeline:
  group:
    - step: MyStep
      module: my_module.steps
```

```{code-block} yaml
:caption: Example step from a file in the project
pipeline:
  group:
    - step: MyStep
      file: steps/my_step.py
```

For simple tasks that can be executed using a single command, one can use the `run` option to define the command to be executed.
For such a step there is no dependency management and no user configuration. These steps are always executed.

```{code-block} yaml
:caption: Example step with a command
pipeline:
  group:
    - step: print_env
      description: print the environment
      run: set
```

````{important}
For executing a command using the `run` option, the command and its arguments shall be provided as a list of strings.
For example:

```{code-block} yaml
:caption: Example command with multiple arguments
pipeline:
  group:
    - step: HelloWorld
      run: [python, -c, "print('Hello World')"]
```
````

In case one provides the `run` option as a string, the command will be automatically split by spaces to form the command and its arguments.
This means that this command will also work:

```{code-block} yaml
:caption: Example command as string
pipeline:
  group:
    - step: Hello
      run: echo "Hello"
```

### Groups (optional)

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

```

```
