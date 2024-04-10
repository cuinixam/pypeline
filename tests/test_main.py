
from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.main import run


def test_run(artifacts_locator: ProjectArtifactsLocator) -> None:
    run(project_dir=artifacts_locator.project_root_dir, step="MyStep", single=True, print=False)
    assert artifacts_locator.build_dir.joinpath("custom/MyStep.deps.json").exists(), "Step dependencies file shall exist"
