from pathlib import Path

from pypeline.domain.artifacts import ProjectArtifactsLocator


def test_pipeline_executor(project: Path) -> None:
    artifacts_locator = ProjectArtifactsLocator(project)
    assert artifacts_locator.project_root_dir == project
    assert artifacts_locator.locate_artifact("pypeline.yaml", []) == project.joinpath("pypeline.yaml")
    # One can provide a list of paths to search for the artifact before the project root directory
    assert artifacts_locator.locate_artifact("pypeline.yaml", [project.joinpath("some_file.txt")]) == project.joinpath("pypeline.yaml")
