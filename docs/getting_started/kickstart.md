# Hello Pypeline!

This guide will walk you through the process of installing Pypeline and kick-starting your first project.

## Installation

To install Pypeline, run the following command:

```bash
pip install pypeline
```

If you cloned the repository, follow the steps in the `README` to bootstrap the project and install the dependencies.

## Kickstart

Pypeline provides a command-line interface (CLI) to help you create a new project. To create a new project, run the following command:

```bash
pypeline init --project-dir <some path>
```

:::{note}
Replace `<some path>` with the path where you want to create the project.
:::

If you cloned the repository, follow the steps in the `README` to install the dependencies and then run:

```powershell
.\pypeline.ps1  init --project-dir <some path>
```

:::{note}
`pypeline.ps1` is a PowerShell script that wraps the Pypeline CLI.
:::

## Check the Project

Navigate to the project directory and check the contents. You should see the following files:

- `pypeline.yaml`: The pipeline definition file
- `steps/`: The directory containing the pipeline steps

To run the pipeline, execute the following command from the project directory:

```powershell
.\pypeline.ps1 run
```

Happy coding!
