# Configure Pipeline Inputs

Parameterize one pipeline definition instead of maintaining near-identical copies — the same file serves every job of a CI matrix or any local what-if run.

## Declare inputs

Declare inputs at the top level of `pypeline.yaml`, similar to GitHub Actions workflow inputs:

```yaml
inputs:
  profile:
    type: string
    description: Check profile to run
    default: quick
  jobs:
    type: integer
    default: 4
  verbose:
    type: boolean
    default: false
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | ✓ | `string`, `integer`, or `boolean` |
| `description` | | Shown in error messages and docs |
| `default` | | Value used when not passed on the CLI |
| `required` | | Fail when missing and no default (default: `false`) |

## Pass values on the command line

```bash
pypeline run -i profile=full -i jobs=8 -i verbose
```

Values are validated against the declared type; without `-i`, the declared `default` applies.

## Use inputs in `run:` commands

Reference inputs with the GitHub-Actions-style `${{ inputs.<name> }}` syntax:

```yaml
inputs:
  profile:
    type: string
    default: quick

pipeline:
  - step: RunChecks
    run: check-tool --profile ${{ inputs.profile }}
```

`pypeline run` uses the default (`quick`); `pypeline run -i profile=full` runs the full profile — same file, no edits.

Rules:

- Only the `inputs.` context is supported — no expressions, functions, or fallbacks (`${{ inputs.x || 'y' }}` is an error; put the fallback in the input's `default`).
- Booleans render lowercase (`true`/`false`), matching GitHub Actions.
- An unknown input name, an input without a value, or a malformed placeholder fails the step with a message naming the step and the offending command — a literal `${{ … }}` is never passed to a subprocess.
- String commands are substituted **before** the command is split into arguments, so quote the placeholder if the value may contain spaces: `--select '${{ inputs.filter }}'` stays one argument. In list form (`run: [check-tool, --select, "${{ inputs.filter }}"]`) every element is one argument already.

## Use inputs in step code

Step classes read inputs through the execution context:

```python
class MyStep(PipelineStep[ExecutionContext]):
    def run(self) -> int:
        profile = self.execution_context.get_input("profile")
        ...
```

`get_input()` returns `None` for undeclared or unset inputs — check before use.
