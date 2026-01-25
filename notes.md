
## Use pypeline for a Python application

The pypeline file:

```{yaml}
inputs:
  python_version:
    type: string
    description: Specify python version for bootstrap
    default:

pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      package_manager: uv>=0
      python_version: 3.13
  - step: GenerateEnvSetupScript
    module: pypeline.steps.env_setup_script
  - step: PreCommit
    run: pre-commit run --all-files
  - step: PyTest
    run: pytest
  - step: Docs
    run: sphinx-build -E -a docs docs/_build
```


### GitHub Actions

GitHub Action workflow job to test the application:

```{yaml}
  test:
    strategy:
      fail-fast: false
      matrix:
        python-version:
          - "3.10"
          - "3.13"
        os:
          - ubuntu-latest
          - windows-latest
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v5
      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install pypeline runner
        run: pip install pypeline-runner>=1.23
        shell: bash
      - name: Run pypeline
        run: pypeline run --input python_version=${{ matrix.python-version }}
        shell: bash
```

### Jenkins file

Jenkinsfile to test the application:

```{groovy}
pipeline {
    agent none

    stages {
        stage('Test Matrix') {
            matrix {
                axes {
                    axis {
                        name 'PYTHON_VERSION'
                        values '3.10', '3.13'
                    }
                    axis {
                        name 'PLATFORM'
                        values 'linux', 'windows'
                    }
                }
                stages {
                    stage('Test') {
                        agent {
                            label "${PLATFORM}"
                        }
                        steps {
                            checkout scm

                            script {
                                if (isUnix()) {
                                    sh """
                                        # Install Python with the specified version
                                        ./scripts/install-python.sh ${PYTHON_VERSION}

                                        # Install pypeline runner
                                        pip install pypeline-runner>=1.23

                                        # Run pypeline
                                        pypeline run --input python_version=${PYTHON_VERSION}
                                    """
                                } else {
                                    bat """
                                        REM Install Python with the specified version
                                        call scripts\\install-python.bat ${PYTHON_VERSION}

                                        REM Install pypeline runner
                                        pip install pypeline-runner>=1.23

                                        REM Run pypeline
                                        pypeline run --input python_version=${PYTHON_VERSION}
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}

```

### Locally on the user machine

```{bash}
pipx install pypeline-runner>=1.23
pypeline run --input python_version=3.13
```

Before opening an IDE, load the setup script:

```{bash}
source ./build/env_setup.sh
```

## Use pypeline for a multi-repo project

The pypeline file:

```{yaml}
pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
    config:
      python_version: 3.13
      python_package_manager: uv>=0.9
  - step: WestInstall
    module: pypeline.steps.west_install
    description: Download external modules
  - step: MyStep
    file: steps/my_step.py
```

This pypeline file can be used to bootstrap a multi-repo project.
It creates the virtual environment and downloads the external modules (git repositories) described in the west manifest.
At last it runs a custom step (MyStep) loaded from the project.


## Use pypeline module as a library

In my project, I have to define a sequence of steps to execute sequentially.
I can use the pypeline core classes to load my steps and execute them.

See the `examples/custom_pipeline.py` file for details. Start reading from the `main` function ;).
To run the example, execute `python examples/custom_pipeline.py`.

```
python examples/custom_pipeline.py

[1] Load and execute the steps from the 'steps.yaml' file
  - Add 5 to 0
  - Multiply 5 by 2
  - Add 2 to 10
Result: 12
Execution context result: 12
[2] Load and execute steps from list
  - Add 10 to 0
  - Multiply 10 by 3
  - Add 2 to 30
Result: 32
Execution context result: 32

```
