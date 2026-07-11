import os
import textwrap
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.config import ProjectConfig
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import RunCommandSpec
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor, parse_run_commands, resolve_input_placeholders


@pytest.mark.parametrize(
    "text, inputs, expected",
    [
        ("--profile ${{ inputs.profile }}", {"profile": "full"}, "--profile full"),
        ("--profile ${{inputs.profile}}", {"profile": "full"}, "--profile full"),
        ("deploy ${{ inputs.target }} --region ${{ inputs.region }}", {"target": "staging", "region": "eu"}, "deploy staging --region eu"),
        ("--verbose ${{ inputs.verbose }}", {"verbose": True}, "--verbose true"),
        ("--jobs ${{ inputs.jobs }}", {"jobs": 4}, "--jobs 4"),
        ("echo 'no placeholders here'", {}, "echo 'no placeholders here'"),
        ("${{ inputs.verbose | flag }}", {"verbose": True}, "--verbose"),
        ("${{ inputs.verbose|flag }}", {"verbose": False}, ""),
    ],
)
def test_resolve_input_placeholders(text: str, inputs: Dict[str, Any], expected: str) -> None:
    assert resolve_input_placeholders(text, inputs, "Step") == expected


@pytest.mark.parametrize(
    "text, inputs, error_match",
    [
        ("--flag ${{ inputs.missing }}", {"other": "x"}, r"unknown input 'missing'"),
        ("echo ${{ env.HOME }}", {}, r"unsupported placeholder"),
        ("--profile ${{ inputs.profile }}", {"profile": None}, r"input 'profile' has no value"),
        ("--flag ${{ inputs.profile }", {"profile": "x"}, r"malformed placeholder"),
        ("${{ inputs.verbose | upper }}", {"verbose": True}, r"unsupported filter 'upper'"),
        ("${{ inputs.profile | flag }}", {"profile": "full"}, r"'flag' filter only applies to boolean inputs"),
    ],
)
def test_resolve_input_placeholders_errors(text: str, inputs: Dict[str, Any], error_match: str) -> None:
    with pytest.raises(UserNotificationException, match=error_match):
        resolve_input_placeholders(text, inputs, "Step")


@pytest.mark.parametrize(
    "run_spec, inputs, expected",
    [
        (
            "check-tool --profile ${{ inputs.profile }}\n\nreport-tool --title '${{ inputs.title }}'\n",
            {"profile": "full", "title": "Nightly Run"},
            [["check-tool", "--profile", "full"], ["report-tool", "--title", "'Nightly Run'" if os.name == "nt" else "Nightly Run"]],
        ),
        (["check-tool", "--select", "${{ inputs.filter }}"], {"filter": "group a"}, [["check-tool", "--select", "group a"]]),
        ("pytest ${{ inputs.verbose | flag }} tests", {"verbose": True}, [["pytest", "--verbose", "tests"]]),
        ("pytest ${{ inputs.verbose | flag }} tests", {"verbose": False}, [["pytest", "tests"]]),
        (["pytest", "${{ inputs.verbose | flag }}", "tests"], {"verbose": True}, [["pytest", "--verbose", "tests"]]),
        (["pytest", "${{ inputs.verbose | flag }}", "tests"], {"verbose": False}, [["pytest", "tests"]]),
        (["check-tool", "--select", ""], {}, [["check-tool", "--select", ""]]),
    ],
)
def test_parse_run_commands(run_spec: RunCommandSpec, inputs: Dict[str, Any], expected: List[List[str]]) -> None:
    assert parse_run_commands(run_spec, inputs, "Step") == expected


def test_parse_run_commands_unparsable_command() -> None:
    with pytest.raises(UserNotificationException, match=r"Step 'Step': could not parse command"):
        parse_run_commands("check-tool 'unclosed", {}, "Step")


def test_run_command_step_resolves_inputs(tmp_path: Path, execution_context: Mock) -> None:
    config_file = tmp_path / "pypeline.yaml"
    config_file.write_text(
        textwrap.dedent("""\
    inputs:
        profile:
            type: string
            default: quick
    pipeline:
        steps:
            - step: RunChecks
              run: check-tool --profile ${{ inputs.profile }}
    """)
    )
    steps_references = PipelineScheduler[ExecutionContext].create_pipeline_loader(ProjectConfig.from_file(config_file).pipeline, tmp_path).load_steps_references()
    execution_context.inputs = {"profile": "full"}

    PipelineStepsExecutor[ExecutionContext](execution_context, steps_references).run()

    assert execution_context.create_process_executor.call_args_list[0].args[0] == ["check-tool", "--profile", "full"]
