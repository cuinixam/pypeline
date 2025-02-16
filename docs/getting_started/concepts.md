# Basic Concepts

## Execution Context

All information required to execute the pipeline steps.
The steps can add information to the execution context to be available for the next steps.

Examples:

- a step installing tools can register tools with their bin folders to be used by subsequent steps
- code generators can provide include paths

## Pipeline Step

The building blocks of a pipeline.
The pipeline steps are implemented as Python modules or command-line scripts.
