Pypeline lets you define your build, test, and deployment pipeline in a single YAML file and run it _consistently_ across your local development environment and _any_ CI/CD platform (GitHub Actions, Jenkins, etc.). No more platform-specific configurations – write once, run anywhere.

**Key Features**

- **Unified Pipeline Definition**: Users can define their entire pipeline in a single YAML file, eliminating the need to switch between different syntaxes and configurations for different CI/CD tools.

- **Extensibility**: Pypeline supports execution steps defined not only through installed Python packages but also from local scripts.

- **Execution Context**: Allow sharing information and state between steps. Each step in the pipeline receives an execution context that can be updated during step execution.

- **Dependency Handling**: Every step can register its dependencies and will only be scheduled if anything has changed.

See the [Getting Started](getting_started/index.md) section to learn how to install and use Pypeline.
