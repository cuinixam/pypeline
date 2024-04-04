from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.config import ProjectConfig


def test_pipeline_executor(artifacts_locator: ProjectArtifactsLocator) -> None:
    config = ProjectConfig.from_file(artifacts_locator.config_file)
    assert config.file == artifacts_locator.config_file
    assert config.pipeline
