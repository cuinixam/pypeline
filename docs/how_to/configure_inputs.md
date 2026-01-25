# Configure Pipeline Inputs

Pass parameters to your pipeline via CLI or define defaults in YAML.

## Define Inputs in YAML

```yaml
inputs:
  environment:
    type: string
    description: Target environment
    default: development
  debug:
    type: boolean
    description: Enable debug mode
    default: false

pipeline:
  - step: Deploy
    file: steps/deploy.py
```

## Pass Inputs via CLI

```shell
pypeline run -i environment=production -i debug=true
```

## Access Inputs in Steps

```python
class DeployStep(PipelineStep[ExecutionContext]):
  def run(self) -> None:
    env = self.execution_context.get_input("environment")
    debug = self.execution_context.get_input("debug")

    if debug:
      print(f"Deploying to {env} with debug enabled")
```

## Input Types

| Type | Example Values |
|------|----------------|
| `string` | `"production"`, `"3.13"` |
| `boolean` | `true`, `false` |
| `integer` | `42`, `100` |
