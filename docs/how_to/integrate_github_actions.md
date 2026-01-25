# Integrate with GitHub Actions

Run your pypeline in GitHub Actions with matrix testing.

## Workflow Configuration

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.13"]
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install pypeline
        run: pip install pypeline-runner>=1.23
        shell: bash

      - name: Run pipeline
        run: pypeline run --input python_version=${{ matrix.python-version }}
        shell: bash
```

## Passing Inputs

Use `--input` to pass matrix values to your pipeline:

```yaml
inputs:
  python_version:
    type: string
    description: Python version for bootstrap
    default: "3.13"

pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      python_version: ${{ inputs.python_version }}
```
