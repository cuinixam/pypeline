# Architecture Overview

Pypeline's design enables CI-agnostic, cross-platform pipeline execution.

## The Problem

Traditional CI pipelines are tightly coupled to specific platforms:
- GitHub Actions workflows don't run on Jenkins
- Jenkins Pipelines don't run locally
- Platform-specific scripts break across Windows/Linux

## The Solution

Pypeline separates **pipeline logic** from **CI execution**:

```{mermaid}
flowchart TB
  subgraph "Your Code"
    yaml[pypeline.yaml]
    steps[Python Steps]
  end

  subgraph "Pypeline"
    loader[PipelineLoader]
    scheduler[PipelineScheduler]
    executor[PipelineStepsExecutor]
  end

  subgraph "Run Anywhere"
    gh[GitHub Actions]
    jenkins[Jenkins]
    local[Local Machine]
  end

  yaml --> loader
  steps --> loader
  loader --> scheduler
  scheduler --> executor

  gh -.-> |pip install pypeline-runner| loader
  jenkins -.-> |pip install pypeline-runner| loader
  local -.-> |pypeline run| loader
```

The key insight: **CI platforms invoke pypeline**, not the other way around. Your pipeline definition stays the same; only the trigger changes.

## Three-Layer Architecture

### 1. Domain Layer

Core abstractions in `pypeline/domain/`:

| Component | Purpose |
|-----------|---------|
| `PipelineStep` | Base class for all steps |
| `ExecutionContext` | Shared state container |
| `PipelineConfig` | Parsed YAML structure |
| `PipelineLoader` | Dynamic step class loading |

### 2. Orchestration Layer

Execution logic in `pypeline/pypeline.py`:

| Component | Purpose |
|-----------|---------|
| `PipelineScheduler` | Filters steps based on CLI args |
| `PipelineStepsExecutor` | Runs steps sequentially |
| `RunCommandClassFactory` | Creates steps from `run:` commands |

### 3. Steps Layer

Built-in and custom steps:

| Step | Purpose |
|------|---------|
| `CreateVEnv` | Python virtual environment setup |
| `WestInstall` | Multi-repo dependency management |
| `ScoopInstall` | Windows package installation |
| `GenerateEnvSetupScript` | Environment setup script generation |
| Custom steps | User-defined logic |

## Design Principles

- **Write once, run anywhere**: Same pipeline on local machine and CI
- **Python-first**: Steps are Python classes, not shell scripts
- **Extensible**: Custom steps for domain-specific needs
- **Dependency-aware**: Smart rebuilds based on inputs/outputs
