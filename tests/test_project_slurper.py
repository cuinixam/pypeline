from pathlib import Path

from pypeline.domain.project_slurper import ProjectSlurper


def test_pipeline_executor(project: Path) -> None:
    project_slurper = ProjectSlurper(project)
    assert project_slurper.project_dir == project
    assert project_slurper.pipeline
