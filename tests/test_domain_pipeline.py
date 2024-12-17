import textwrap
from pathlib import Path

from pypeline.domain.config import ProjectConfig
from pypeline.domain.pipeline import PipelineConfigIterator


def test_pipeline_iterator_without_groups(tmp_path: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = tmp_path / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                - step: MyStep
                  file: my_python_file.py
                  config:
                    input: value
                - step: ScoopInstall
                  module: pypeline.steps.scoop_install
                - step: Echo
                  run: echo 'Hello'
                  description: Simple step that runs a command
            """
        )
    )
    pipeline_config = ProjectConfig.from_file(pypeline_config).pipeline
    # Consume the iterator
    assert [None] == [item[0] for item in PipelineConfigIterator(pipeline_config)]


def test_pipeline_iterator_with_groups(tmp_path: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = tmp_path / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                group1:
                  - step: ScoopInstall
                    module: pypeline.steps.scoop_install
                group2:
                  - step: Echo
                    run: echo 'Hello'
                    description: Simple step that runs a command
            """
        )
    )
    pipeline_config = ProjectConfig.from_file(pypeline_config).pipeline
    # Consume the iterator
    assert ["group1", "group2"] == [item[0] for item in PipelineConfigIterator(pipeline_config)]
