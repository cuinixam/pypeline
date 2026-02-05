# Pypeline Project Instructions

## Architecture Overview

Pypeline is a cross-platform, CI-agnostic pipeline framework (similar to GitHub Actions or GitLab CI) that lets you define build/test/deploy pipelines in YAML **once** and run them identically on local machines and any CI system (Jenkins, GitHub Actions, etc.).
The key difference: pipeline steps are Python classes instead of platform-specific scripts, ensuring reproducible builds and eliminating "works locally, fails in CI" problems.

### Architectural Layers

The architecture follows a clean separation of concerns with three main layers:

1. **Domain Layer** (`src/pypeline/domain/`)
   - **Core abstractions**: `PipelineStep` (base class for all steps), `ExecutionContext` (shared state), `PipelineConfig` (YAML structure)
   - **Pipeline loading**: `PipelineLoader` dynamically loads steps from modules/files/commands
   - **Configuration parsing**: `ProjectSlurper` reads `pypeline.yaml` and validates inputs
   - **Artifact management**: `ProjectArtifactsLocator` standardizes build output paths

2. **Orchestration Layer** (`src/pypeline/pypeline.py`)
   - **PipelineScheduler**: Filters which steps to execute based on CLI args (supports `--step`, `--single` flags)
   - **PipelineStepsExecutor**: Runs steps sequentially, manages dependency checks, calls `update_execution_context()` after each step
   - **RunCommandClassFactory**: Dynamically creates step classes for `run:` commands in YAML config

3. **Steps Layer** (`src/pypeline/steps/` and user-defined)
   - **Built-in steps**: `CreateVEnv`, `WestInstall`, `ScoopInstall`, `EnvSetupScript`
   - **Custom steps**: User-defined classes in project's `steps/` directory
   - **Command steps**: Shell commands defined inline via `run:` field in YAML

### Key Concepts

**PipelineStep** is the fundamental building block. Every step inherits from `PipelineStep[ExecutionContext]` and implements:

- `run()`: Execute the step's business logic (returns exit code)
- `get_inputs()/get_outputs()`: Declare file dependencies for smart rebuilds (Runnable framework checks these)
- `update_execution_context()`: Share state with subsequent steps (called **every time**, even if step skipped)
- `get_needs_dependency_management()`: Return `False` to force step execution regardless of dependencies

**ExecutionContext** is the shared state container passed to all steps (see [pypeline-steps skill](.agent/skills/pypeline-steps/SKILL.md) for usage examples):

- `install_dirs: List[Path]`: Binary directories automatically added to subprocess PATH
- `data_registry: DataRegistry`: Type-safe key-value store for arbitrary data exchange
- `inputs: Dict[str, Any]`: User parameters from CLI (`-i key=value`) or config defaults
- `env_vars: Dict[str, Any]`: Environment variables injected into all subprocess calls
- `create_process_executor()`: Factory method that configures subprocess with PATH/env from context

**Dynamic Step Loading** supports three patterns in YAML config:

- `module`: Load class from installed Python package (`module: pypeline.steps.create_venv`, `step: CreateVEnv`)
- `file`: Load class from project-local script (`file: steps/my_step.py`, `step: MyStep`)
- `run`: Execute shell command directly (`run: [echo, "Hello"]` or `run: "pytest -v"`) — auto-generates step class

**Pipeline Execution Flow**:

1. CLI (`main.py`) → `ProjectSlurper` reads `pypeline.yaml`
2. `InputsParser` validates and parses CLI inputs against config schema
3. `PipelineScheduler` filters steps based on `--step`/`--single` flags
4. `PipelineLoader` dynamically loads step classes (from modules, files, or creates command wrappers)
5. `PipelineStepsExecutor` runs each step:
   - Creates step instance with `ExecutionContext`
   - `Executor` (from `py_app_dev`) checks input/output dependencies (unless `get_needs_dependency_management()` returns `False`)
   - Calls `step.run()` if outdated or forced
   - **Always** calls `step.update_execution_context()` to propagate state
6. Subprocess execution automatically uses `ExecutionContext.install_dirs` in PATH and `env_vars` in environment

## Extensibility & CI-Agnostic Design

Pypeline solves the software product line problem where pipelines become tightly coupled to specific CI systems (Jenkins, GitHub Actions, etc.). Each CI system has its own syntax and limitations, making pipelines non-portable.

**Design Principles:**

- **CI System Independence**: Pipeline logic lives in Python steps, not CI-specific YAML/scripts
- **Cross-Platform Execution**: Same pipeline runs identically on Windows, Linux, macOS
- **Local Development Parity**: Developers can run the exact same pipeline locally as in CI
- **Custom Step Focus**: While built-in steps handle common patterns, the framework is designed for users to create domain-specific steps tailored to their needs

**Built-in vs Custom Steps**: The predefined steps in `src/pypeline/steps/` are starting points. Most real-world pipelines will require custom steps that encapsulate project-specific build processes, testing frameworks, or deployment procedures.

## Development Patterns

### Creating Pipeline Steps

> **📖 Reference**: For detailed examples of creating custom steps, using ExecutionContext, DataRegistry patterns, and step configuration, see [pypeline-steps skill](.agent/skills/pypeline-steps/SKILL.md).

Follow the template in `src/pypeline/kickstart/templates/project/steps/my_step.py`:

```python
class MyStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        # Access shared state and inputs
        logger.info(f"Install dirs: {self.execution_context.install_dirs}")
        user_input = self.execution_context.get_input('my_param')

    def update_execution_context(self) -> None:
        # Update shared state for subsequent steps
        self.execution_context.add_install_dirs([Path("/new/install/dir")])
```

### Configuration Structure

> **📖 Reference**: For complete YAML configuration examples including inputs, step loading patterns, and running pipelines, see [pypeline-steps skill](.agent/skills/pypeline-steps/SKILL.md).

Pipeline configs in `pypeline.yaml` support both flat lists and grouped steps:

```yaml
inputs:
  environment:
    type: string
    description: Target environment
    default: development

pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      python_package_manager: uv>=0.6
  - step: CustomStep
    file: steps/custom.py
```

### Testing Conventions

Tests use `conftest.py` fixtures for consistent setup:

- `project(tmp_path)`: Creates test project with sample step files
- `artifacts_locator`: Provides build directory management
- Test step classes in conftest demonstrate data registry usage patterns

## Developer Workflows

### Environment Setup

```bash
pipx install pypeline-runner  # Install pypeline globally
pypeline run                   # Creates .venv and installs dependencies
```

### Running Tasks

Use VS Code tasks or Python commands:

- **Tests**: `.venv/bin/python -m pytest --cov` (Task: "run tests")
- **Pre-commit**: `.venv/bin/python -m pre-commit run --all-files` (Task: "run pre-commit checks")
- **Docs**: `.venv/bin/python -m sphinx-build -E -a docs docs/_build` (Task: "generate docs")

### Package Management

> [!CAUTION]
> **This project uses Poetry.** Check for `poetry.lock` before managing dependencies.

```bash
source build/env_setup.sh              # Get access to Poetry first
poetry add package_name@latest --no-cache  # Add/update packages
```

### CLI Usage Patterns

```bash
pypeline init --project-dir my-project  # Bootstrap new project
pypeline run --step MyStep --single     # Run specific step only
pypeline run --step MyStep              # Run up to MyStep
pypeline run -i param=value             # Pass input parameters
```

## Integration Points

**External Dependencies**:

- `py-app-dev`: Provides subprocess execution, logging, and runnable framework
- `west`: Nordic's meta-tool for managing multiple repositories
- Built-in steps handle common patterns (venv creation, package management)

**Subprocess Execution**: ExecutionContext automatically configures PATH with install directories and passes environment variables to all subprocess calls.

**Artifact Management**: `ProjectArtifactsLocator` standardizes paths:

- Build outputs → `build/`
- Virtual environments → `.venv/`
- External deps → `build/external/`

## Project-Specific Conventions

- Step classes use generic typing: `PipelineStep[ExecutionContext]`
- Configuration uses Mashumaro dataclasses with `DataClassDictMixin`
- Error handling via `UserNotificationException` for user-facing errors
- **Cross-platform compatibility**: Always use `pathlib.Path`, handle Windows/Unix differences in `ProjectArtifactsLocator`, and test shell parameter in subprocess execution
- **CI-agnostic subprocess execution**: ExecutionContext handles PATH manipulation and environment variables uniformly across platforms
- Package name mismatch: PyPI package is `pypeline-runner`, CLI command is `pypeline`
- **Mashumaro serialization**: When fields need different key names in output (e.g., `url_base` → `url-base` for YAML), use field aliases with `metadata={"alias": "key-name"}` and create a mixin with `serialize_by_alias = True`. Never manually convert keys after calling `to_dict()`.

## Coding Guidelines

- Always include full **type hints** (functions, methods, public attrs, constants).
- Prefer **pythonic** constructs: context managers, `pathlib`, comprehensions when clear, `enumerate`, `zip`, early returns, no over-nesting.
- Follow **SOLID**: single responsibility; prefer composition; program to interfaces (`Protocol`/ABC); inject dependencies.
- **Naming**: descriptive `snake_case` vars/funcs, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Avoid single-letter identifiers (including `i`, `j`, `a`, `b`) except in tight math helpers.
- Code should be **self-documenting**. Use docstrings only for public APIs or non-obvious rationale/constraints; avoid noisy inline comments.
- Errors: raise specific exceptions; never `except:` bare; add actionable context.
- Imports: no wildcard; group stdlib/third-party/local, keep modules small and cohesive.
- Testability: pure functions where possible; pass dependencies, avoid globals/singletons.
- tests: use `pytest`; keep the tests to a minimum; use parametrized tests when possible; do no add useless comments; the tests shall be self-explanatory.
- pytest fixtures: use them to avoid code duplication; use `conftest.py` for shared fixtures. Use `tmp_path` in case of file system operations.

## Code Quality Rules

> [!IMPORTANT]
> **Follow these professional coding standards in all code.**

1. **Import Placement**: ALL imports MUST be at the top of the file
   - NEVER import modules inside functions or methods
   - Group imports: standard library, third-party, local
   - Use alphabetical ordering within groups
   - This is basic professional Python development

## Non-Negotiable Development Rules

> [!CAUTION]
> **These rules MUST be followed for all code changes. No exceptions.**

### Plan Before Implementation

1. **Always Present a Plan First**: Before making ANY code changes:
   - Present a clear implementation plan describing WHAT will be changed and HOW
   - Wait for explicit user approval before proceeding with implementation
   - Never jump straight to coding, even for seemingly simple changes

2. **Plan Contents Must Include**:
   - Files to be modified/created/deleted
   - Key changes in each file
   - Any design decisions or trade-offs
   - Testing approach

3. **No Exceptions**: Even if the user has already discussed an approach, always confirm the plan before execution. The user must explicitly approve before any code is written.

### Test-First Development

1. **Write Tests Before Implementation**: For any new functionality or bug fix:
   - Write a **meaningful test** that demonstrates the desired behavior or exposes the bug
   - Then implement the code to make the test pass
   - Tests should be **self-explanatory** - clear test names and minimal comments

2. **Quality Over Quantity**:
   - **Less is better**: Write only meaningful tests that add value
   - Avoid redundant or trivial tests that don't catch real issues
   - Each test should verify a specific behavior or edge case
   - Use parametrized tests to cover multiple scenarios efficiently

3. **Test Coverage Philosophy**:
   - Focus on testing **behavior**, not implementation details
   - Critical paths and business logic MUST have tests
   - Trivial getters/setters don't need tests
   - Integration tests for step classes and pipeline interactions

### Validation Requirements

1. **Run Full Pipeline**: After making changes, **ALWAYS** run:

   ```bash
   pypeline run
   ```

   This executes:
   - Virtual environment setup
   - Pre-commit hooks (linting, type checking)
   - All tests
   - Code quality checks

2. **Pre-Commit Compliance**: Code MUST pass all pre-commit checks:
   - `ruff` (linting)
   - `mypy` (type checking)
   - `codespell` (spelling)
   - All other configured hooks

3. **No Shortcuts**: Do not commit code that:
   - Bypasses tests
   - Fails linting or type checking
   - Breaks existing functionality
   - Lacks test coverage for critical functionality

### Definition of Done

1. **Acceptance Criteria**: Changes are NOT complete until:
   - `pypeline run` executes with **zero failures**
   - All pre-commit checks pass
   - New functionality has appropriate test coverage
