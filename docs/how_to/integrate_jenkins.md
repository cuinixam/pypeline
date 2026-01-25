# Integrate with Jenkins

Run the same pypeline on Jenkins with cross-platform support.

## Jenkinsfile

```groovy
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
            agent { label "${PLATFORM}" }
            steps {
              checkout scm
              script {
                if (isUnix()) {
                  sh """
                    pip install pypeline-runner>=1.23
                    pypeline run --input python_version=${PYTHON_VERSION}
                  """
                } else {
                  bat """
                    pip install pypeline-runner>=1.23
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

## Key Points

- Same `pypeline.yaml` works on both Jenkins and GitHub Actions
- Use `--input` to pass build parameters
- Cross-platform: pypeline handles Windows/Linux differences internally
