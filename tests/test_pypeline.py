import os
import textwrap
from pathlib import Path
from typing import List, Optional, OrderedDict, Type, cast
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.config import ProjectConfig
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineConfig, PipelineStep, PipelineStepConfig, PipelineStepReference
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor, RunCommandClassFactory
from tests.conftest import assert_element_of_type


@pytest.fixture
def pipeline_config(project: Path) -> PipelineConfig:
    return ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline


def test_pipeline_loader(project: Path, pipeline_config: PipelineConfig) -> None:
    steps_references = PipelineScheduler[ExecutionContext].create_pipeline_loader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo", "CheckPython"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_loader_without_groups(project: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = project / "pypeline.yaml"
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
    pipeline_config = ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline
    steps_references = PipelineScheduler[ExecutionContext].create_pipeline_loader(pipeline_config, project).load_steps_references()
    assert [step_ref.name for step_ref in steps_references] == ["MyStep", "ScoopInstall", "Echo"]
    assert steps_references[0].config == {"input": "value"}
    assert steps_references[1].config is None


def test_pipeline_only_load_the_step_to_be_executed(project: Path) -> None:
    # Create pypeline configuration without groups
    pypeline_config = project / "pypeline.yaml"
    pypeline_config.write_text(
        textwrap.dedent(
            """\
            pipeline:
                - step: MyStep
                  file: my_python_file.py
                  config:
                    input: value
                - step: IDoNotExist
                  module: do.not.exist
            """
        )
    )
    pipeline_config = ProjectConfig.from_file(ProjectArtifactsLocator(project).config_file).pipeline
    steps_to_run = PipelineScheduler[ExecutionContext](pipeline_config, project).get_steps_to_run(["MyStep"], single=True)
    assert [step.name for step in steps_to_run] == ["MyStep"]


def test_pipeline_loader_run_command(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Echo
              run: echo "Hello"
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"
    # Execute the step
    executor = PipelineStepsExecutor[ExecutionContext](ExecutionContext(tmp_path), steps_references)
    executor.run()


def test_pipeline_loader_run_command_with_list(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Echo
              run: [python, -c, "print('Hello World')"]
              description: Simple step that runs a command
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "Echo"
    step = step_ref._class(Mock(), Mock())
    assert step.get_name() == "Echo"
    # Execute the step
    executor = PipelineStepsExecutor[ExecutionContext](ExecutionContext(tmp_path), steps_references)
    executor.run()


def test_pipeline_loader_run_multiline(tmp_path: Path, execution_context: Mock) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: QualityChecks
              run: |
                python --version
                python -c "print('done')"
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "QualityChecks"
    executor = PipelineStepsExecutor[ExecutionContext](execution_context, steps_references)
    executor.run()

    assert execution_context.create_process_executor.call_count == 2
    assert execution_context.create_process_executor.call_args_list[0].args[0] == ["python", "--version"]
    expected_arg = "\"print('done')\"" if os.name == "nt" else "print('done')"
    assert execution_context.create_process_executor.call_args_list[1].args[0] == ["python", "-c", expected_arg]
    assert execution_context.create_process_executor.return_value.execute.call_count == 2


def test_pipeline_loader_run_multiline_skips_empty_lines(tmp_path: Path, execution_context: Mock) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: MultiCmd
              run: |
                python --version

                python -c "print('hello')"
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    step_ref = assert_element_of_type(steps_references, PipelineStepReference)
    assert step_ref.name == "MultiCmd"
    executor = PipelineStepsExecutor[ExecutionContext](execution_context, steps_references)
    executor.run()

    assert execution_context.create_process_executor.call_count == 2
    assert execution_context.create_process_executor.call_args_list[0].args[0] == ["python", "--version"]
    expected_arg = "\"print('hello')\"" if os.name == "nt" else "print('hello')"
    assert execution_context.create_process_executor.call_args_list[1].args[0] == ["python", "-c", expected_arg]
    assert execution_context.create_process_executor.return_value.execute.call_count == 2


def test_pipeline_loader_run_empty_block_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: Empty
              run: |

    """)
    )
    with pytest.raises(UserNotificationException, match="empty `run` block"):
        PipelineScheduler[ExecutionContext].create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        ).load_steps_references()


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific backslash handling")
def test_pipeline_loader_run_preserves_backslashes_on_windows(tmp_path: Path, execution_context: Mock) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    pipeline:
        steps:
            - step: WinPath
              run: some-tool C:\\Users\\foo\\bar
    """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            tmp_path,
        )
        .load_steps_references()
    )
    assert_element_of_type(steps_references, PipelineStepReference)
    executor = PipelineStepsExecutor[ExecutionContext](execution_context, steps_references)
    executor.run()

    assert execution_context.create_process_executor.call_args_list[0].args[0] == ["some-tool", "C:\\Users\\foo\\bar"]


def test_pipeline_create_run_command_step_class(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor[ExecutionContext](
        execution_context,
        [
            PipelineStepReference("my_cmd", cast(Type[PipelineStep[ExecutionContext]], RunCommandClassFactory._create_run_commands_step_class([["echo 'Hello'"]], "Echo"))),
        ],
    )
    executor.run()
    assert not len(list(execution_context.project_root_dir.glob("build/my_cmd/*.deps.json"))), "Step dependencies file shall not exist"


@pytest.mark.parametrize(
    "step_names, single, expected_steps",
    [
        ([], False, ["MyStep", "ScoopInstall", "Echo", "CheckPython"]),  # All steps
        (["ScoopInstall"], True, ["ScoopInstall"]),  # Single step
        (["ScoopInstall"], False, ["MyStep", "ScoopInstall"]),  # Steps up to the selected step
        (["MyStep"], False, ["MyStep"]),  # Run the first step only
        (["MyStep", "CheckPython"], True, ["MyStep", "CheckPython"]),  # Multiple selected steps
        (["MyStep", "Echo"], False, ["MyStep", "ScoopInstall", "Echo"]),  # Steps up to "Echo"
        (["Echo"], True, ["Echo"]),  # Single "Echo"
    ],
)
def test_pipeline_scheduler(project: Path, pipeline_config: PipelineConfig, step_names: List[str], single: bool, expected_steps: List[str]) -> None:
    scheduler = PipelineScheduler[ExecutionContext](pipeline_config, project)
    steps_references = scheduler.get_steps_to_run(step_names=step_names, single=single)
    assert [step_ref.name for step_ref in steps_references] == expected_steps


@pytest.mark.parametrize(
    "step_names, single",
    [
        (["MissingStep"], True),
        (["MyStep", "CheckPython", "MissingStep"], True),
        (["MyStep", "CheckPython", "MissingStep"], False),
    ],
)
def test_pipeline_scheduler_exceptions(project: Path, pipeline_config: PipelineConfig, step_names: List[str], single: bool) -> None:
    scheduler = PipelineScheduler[ExecutionContext](pipeline_config, project)
    with pytest.raises(UserNotificationException):
        scheduler.get_steps_to_run(step_names=step_names, single=single)


class MyCustomPipelineStep(PipelineStep[ExecutionContext]):
    def run(self) -> int:
        return 0

    def get_name(self) -> str:
        return "MyCustomPipelineStep"

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        self.execution_context.add_install_dirs([Path("my_install_dir")])


def test_pipeline_executor(execution_context: ExecutionContext) -> None:
    executor = PipelineStepsExecutor(execution_context, [PipelineStepReference("MyStep", cast(Type[PipelineStep[ExecutionContext]], MyCustomPipelineStep))])
    executor.run()
    assert execution_context.project_root_dir.joinpath("build/MyStep/MyCustomPipelineStep.deps.json").exists(), "Step dependencies file shall exist"


class MyExecutionContext(ExecutionContext):
    def __init__(self, project_root_dir: Path, extra_info: str) -> None:
        super().__init__(project_root_dir=project_root_dir)
        self.extra_info = extra_info


class MyCustomPipelineStepWithContext(PipelineStep[MyExecutionContext]):
    def run(self) -> int:
        return 0

    def get_name(self) -> str:
        return "MyCustomPipelineStepWithContext"

    def get_inputs(self) -> List[Path]:
        return []

    def get_outputs(self) -> List[Path]:
        return []

    def update_execution_context(self) -> None:
        self.execution_context.extra_info = "updated"


def test_pipeline_executor_with_custom_context(project: Path) -> None:
    execution_context = MyExecutionContext(project, "initial")
    executor = PipelineStepsExecutor(
        execution_context,
        [PipelineStepReference("MyStep", cast(Type[PipelineStep[MyExecutionContext]], MyCustomPipelineStepWithContext))],
    )
    executor.run()
    assert execution_context.extra_info == "updated"


def test_pipeline_exchange_information_between_steps(project: Path) -> None:
    config_file = project / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: MyStep
                  file: my_python_file.py
                - step: MyStepChecker
                  file: my_python_file.py
            """)
    )
    steps_references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(
            ProjectConfig.from_file(config_file).pipeline,
            project,
        )
        .load_steps_references()
    )
    # Execute pypeline
    execution_context = ExecutionContext(project)
    executor = PipelineStepsExecutor[ExecutionContext](execution_context, steps_references)
    executor.run()
    my_data = [entry for entries in execution_context.data_registry._registry.values() for entry in entries if entry.provider_name == "MyStep"]
    assert len(my_data) == 1, "MyData shall be inserted in the data registry"


def test_project_config_records_source_location(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Echo
                  run: echo "Hello"
            """)
    )
    project_config = ProjectConfig.from_file(config_file)
    assert project_config.file == config_file
    assert project_config.location is not None and project_config.location.file == config_file
    step = cast(List[PipelineStepConfig], project_config.pipeline)[0]
    assert step.location is not None
    assert (step.location.file, step.location.line) == (config_file, 2)


def test_malformed_step_reports_its_location(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Good
                  run: echo "Hello"
                - step: Bad
                  timeout_sec: not-a-number
            """)
    )
    with pytest.raises(UserNotificationException) as exc_info:
        ProjectConfig.from_file(config_file)
    # The error points at the offending step (line 4), not the top of the file.
    assert f"{config_file}:4:" in str(exc_info.value)


def test_malformed_input_reports_its_location(tmp_path: Path) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            inputs:
                env:
                    type: not-a-valid-type
            pipeline:
                - step: Echo
                  run: echo "Hello"
            """)
    )
    with pytest.raises(UserNotificationException) as exc_info:
        ProjectConfig.from_file(config_file)
    assert f"{config_file}:3:" in str(exc_info.value)


def test_missing_config_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ProjectConfig.from_file(tmp_path / "does_not_exist.yaml")


def _loaded_group_of(config_file: Path, step_name: str) -> Optional[str]:
    """The output group a loaded step resolves to (the value that drives output_dir)."""
    references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(ProjectConfig.from_file(config_file).pipeline, config_file.parent)
        .load_steps_references()
    )
    return next(ref.group_name for ref in references if ref.name == step_name)


def test_included_step_output_group_is_identical_standalone_and_included(tmp_path: Path) -> None:
    # The invariant: a fragment's step must land in the same output dir whether the fragment
    # is run on its own or spliced into a group of a larger pipeline, so its cache is shared.
    fragment = tmp_path / "bootstrap.pypeline.yaml"
    fragment.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Bootstrap
                  run: echo "bootstrap"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                setup:
                    - include: bootstrap.pypeline.yaml
                build:
                    - step: Build
                      run: echo "build"
            """)
    )
    # Standalone: the flat fragment puts Bootstrap in no group.
    assert _loaded_group_of(fragment, "Bootstrap") is None
    # Included into the 'setup' group: the parent group must NOT reach Bootstrap's output identity.
    assert _loaded_group_of(main, "Bootstrap") is None
    # The main pipeline's own grouped step is unaffected.
    assert _loaded_group_of(main, "Build") == "build"


def test_single_file_grouped_output_group_unchanged(tmp_path: Path) -> None:
    # Regression guard: with no includes, a grouped step's output group is its declared group.
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            pipeline:
                gen:
                    - step: Generate
                      run: echo "gen"
            """)
    )
    assert _loaded_group_of(config_file, "Generate") == "gen"


def test_include_splices_in_position_order(tmp_path: Path) -> None:
    fragment = tmp_path / "bootstrap.pypeline.yaml"
    fragment.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: CreateVEnv
                  run: echo "venv"
                - step: InstallDeps
                  run: echo "deps"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Before
                  run: echo "before"
                - include: bootstrap.pypeline.yaml
                - step: After
                  run: echo "after"
            """)
    )
    references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(ProjectConfig.from_file(main).pipeline, tmp_path)
        .load_steps_references()
    )
    assert [ref.name for ref in references] == ["Before", "CreateVEnv", "InstallDeps", "After"]


def test_transitive_include(tmp_path: Path) -> None:
    (tmp_path / "c.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: C
                  run: echo "c"
            """)
    )
    (tmp_path / "b.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - include: c.pypeline.yaml
                - step: B
                  run: echo "b"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include: b.pypeline.yaml
                - step: A
                  run: echo "a"
            """)
    )
    references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(ProjectConfig.from_file(main).pipeline, tmp_path)
        .load_steps_references()
    )
    assert [ref.name for ref in references] == ["C", "B", "A"]


def test_include_cycle_raises(tmp_path: Path) -> None:
    (tmp_path / "a.pypeline.yaml").write_text("pipeline:\n  - include: b.pypeline.yaml\n")
    (tmp_path / "b.pypeline.yaml").write_text("pipeline:\n  - include: a.pypeline.yaml\n")
    with pytest.raises(UserNotificationException, match="(?i)circular|cycle"):
        ProjectConfig.from_file(tmp_path / "a.pypeline.yaml")


def test_include_path_is_relative_to_including_file(tmp_path: Path) -> None:
    sub = tmp_path / "fragments"
    sub.mkdir()
    (sub / "tools.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - include: install.pypeline.yaml
            """)
    )
    (sub / "install.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Install
                  run: echo "install"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include: fragments/tools.pypeline.yaml
            """)
    )
    references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(ProjectConfig.from_file(main).pipeline, tmp_path)
        .load_steps_references()
    )
    assert [ref.name for ref in references] == ["Install"]


def test_included_step_carries_fragment_provenance(tmp_path: Path) -> None:
    fragment = tmp_path / "bootstrap.pypeline.yaml"
    fragment.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Bootstrap
                  run: echo "bootstrap"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include: bootstrap.pypeline.yaml
            """)
    )
    steps = cast(List[PipelineStepConfig], ProjectConfig.from_file(main).pipeline)
    assert steps[0].step == "Bootstrap"
    assert steps[0].location is not None and steps[0].location.file == fragment


def test_grouped_fragment_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "grouped.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                setup:
                    - step: Setup
                      run: echo "setup"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include: grouped.pypeline.yaml
            """)
    )
    with pytest.raises(UserNotificationException, match="(?i)flat|group"):
        ProjectConfig.from_file(main)


def test_include_with_steps_filter_splices_only_named_steps_in_fragment_order(tmp_path: Path) -> None:
    fragment = tmp_path / "bootstrap.pypeline.yaml"
    fragment.write_text(
        textwrap.dedent("""\
            pipeline:
                - step: CreateVEnv
                  run: echo "venv"
                - step: InstallDeps
                  run: echo "deps"
                - step: GenerateSetupScript
                  run: echo "setup"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include:
                    file: bootstrap.pypeline.yaml
                    steps: [GenerateSetupScript, CreateVEnv]
            """)
    )
    references = (
        PipelineScheduler[ExecutionContext]
        .create_pipeline_loader(ProjectConfig.from_file(main).pipeline, tmp_path)
        .load_steps_references()
    )
    assert [ref.name for ref in references] == ["CreateVEnv", "GenerateSetupScript"]


def test_include_with_unknown_step_in_filter_raises(tmp_path: Path) -> None:
    (tmp_path / "bootstrap.pypeline.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: CreateVEnv
                  run: echo "venv"
            """)
    )
    main = tmp_path / "pypeline.yaml"
    main.write_text(
        textwrap.dedent("""\
            pipeline:
                - include:
                    file: bootstrap.pypeline.yaml
                    steps: [DoesNotExist]
            """)
    )
    with pytest.raises(UserNotificationException, match="(?i)DoesNotExist"):
        ProjectConfig.from_file(main)


@pytest.mark.parametrize(
    "entry",
    [
        "- step: Both\n      include: other.pypeline.yaml\n      run: echo hi",  # step + include
        "- description: neither a step nor an include",  # neither
    ],
)
def test_invalid_pipeline_entry_is_rejected(tmp_path: Path, entry: str) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(f"pipeline:\n    {entry}\n")
    with pytest.raises(UserNotificationException):
        ProjectConfig.from_file(config_file)


@pytest.fixture
def sample_steps() -> List[PipelineStepConfig]:
    """Sample pipeline steps for testing."""
    return [
        PipelineStepConfig(step="Step1", module="test.module"),
        PipelineStepConfig(step="Step2", module="test.module"),
        PipelineStepConfig(step="Step3", module="test.module"),
        PipelineStepConfig(step="Step4", module="test.module"),
    ]


@pytest.mark.parametrize(
    "step_names, single, expected_steps",
    [
        (["Step1"], True, ["Step1"]),
        (["Step2"], True, ["Step2"]),
        (["Step1", "Step3"], True, ["Step1", "Step3"]),
        (["Step1"], False, ["Step1"]),
        (["Step2"], False, ["Step1", "Step2"]),
    ],
)
def test_filter_steps(sample_steps: List[PipelineStepConfig], step_names: List[str], single: bool, expected_steps: List[str]) -> None:
    result = cast(List[PipelineStepConfig], PipelineScheduler.filter_steps(sample_steps, step_names, single))
    assert len(result) == len(expected_steps)
    assert [step.step for step in result] == expected_steps


@pytest.fixture
def sample_ordered_dict_config() -> OrderedDict[str, List[PipelineStepConfig]]:
    """Sample OrderedDict pipeline configuration for testing."""
    return OrderedDict(
        [
            (
                "group1",
                [
                    PipelineStepConfig(step="Step1", module="test.module"),
                    PipelineStepConfig(step="Step2", module="test.module"),
                ],
            ),
            (
                "group2",
                [
                    PipelineStepConfig(step="Step3", module="test.module"),
                    PipelineStepConfig(step="Step4", module="test.module"),
                ],
            ),
        ]
    )


def test_filter_steps_with_group(sample_ordered_dict_config: OrderedDict[str, List[PipelineStepConfig]]) -> None:
    result = cast(OrderedDict[str, List[PipelineStepConfig]], PipelineScheduler.filter_steps(sample_ordered_dict_config, ["Step2"], True))
    assert result == OrderedDict(
        [
            (
                "group1",
                [
                    PipelineStepConfig(step="Step2", module="test.module"),
                ],
            )
        ]
    )


def test_filter_multiple_steps_with_group(sample_ordered_dict_config: OrderedDict[str, List[PipelineStepConfig]]) -> None:
    result = cast(OrderedDict[str, List[PipelineStepConfig]], PipelineScheduler.filter_steps(sample_ordered_dict_config, ["Step2", "Step3"], True))
    assert result == OrderedDict(
        [
            (
                "group1",
                [
                    PipelineStepConfig(step="Step2", module="test.module"),
                ],
            ),
            (
                "group2",
                [
                    PipelineStepConfig(step="Step3", module="test.module"),
                ],
            ),
        ]
    )


def test_filter_steps_missing_step_raises_exception(sample_steps: List[PipelineStepConfig]) -> None:
    with pytest.raises(UserNotificationException) as exc_info:
        PipelineScheduler.filter_steps(sample_steps[:2], ["MissingStep"], True)

    assert "Steps not found in pipeline configuration: MissingStep" in str(exc_info.value)
