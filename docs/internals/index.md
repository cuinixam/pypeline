# 📚 Internals

## Design

Add here some documentation for your design.

## Brainstorming

```
bootstrap.json

{
	"install_script": "https://bootstrap.de/install.ps1"
	"version": "v1.2.0"
}


pypeline.yaml

pipeline:
  install:
    - step: ScoopInstall
      module: pypeline.steps.scoop_install
	  config:
		file: scoopfile.json
    - step: WestInstall
      module: pypeline.steps.west_install
  test:
    - step: PyTest
      module: pypeline.steps.execute_tests
  release:
    - step: SemanticVersioning
      module: pypeline.steps.update_version
    - step: DeployEngWeb
      module: pypeline.steps.deploy


build.ps1

- start bootstrap
- run pypeline


pypeline.ps1

- calls pypeline

```

### Generic pipeline dependencies

**Artifacts Locator**

This is required to find custom pipeline steps defined in `.py` files inside the project.

```yaml
pipeline:
  - step: MyStep
    file: scripts/steps/my_step.py
```

**Execution Context**

All information required to execute the pipeline steps.
The steps can add information to the execution context to be available for the next steps.

Examples:

- a step installing tools can register tools with their bin folders to be used by subsequent steps
- code generators can provide include paths

**User Request**

Information about a specific `request` that a user wants to execute.
This is relevant for local builds, where a user might want to execute specific targets.
One might only want to execute a compile for a component or a specific code generation step.

**Pipeline Step**

The building blocks of a pipeline.

**Pipeline Step Reference**

This is just the name of the step. One needs this to be able to distinguish between finding a step and instantiating and executing a step.

**Project Slurper**

This is required to find all relevant configuration files.
If one decides to use multiple configuration files, to define pipeline steps, the project slurper shall be used to find all of them.

### Feature proposals
