from typing import Any, Dict

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.config import ProjectInput
from pypeline.inputs_parser import InputsParser


@pytest.fixture
def basic_definitions() -> Dict[str, ProjectInput]:
    return {
        "username": ProjectInput(type="string", required=True, default=None, description="User name"),
        "retry": ProjectInput(type="integer", required=False, default=3, description="Retry count"),
        "verbose": ProjectInput(type="boolean", required=False, default=False, description="Enable verbose mode"),
    }


@pytest.mark.parametrize(
    "args,expected",
    [
        (["username=john"], {"username": "john", "retry": 3, "verbose": False}),
        (["username=alice", "retry=5"], {"username": "alice", "retry": 5, "verbose": False}),
        (["username=bob", "verbose=true"], {"username": "bob", "retry": 3, "verbose": True}),
        (["username=eve", "verbose=0"], {"username": "eve", "retry": 3, "verbose": False}),
    ],
)
def test_valid_inputs(
    basic_definitions: Dict[str, ProjectInput],
    args: list[str],
    expected: Dict[str, Any],
) -> None:
    parser = InputsParser.from_inputs_definitions(basic_definitions)
    result = parser.parse_inputs(args)
    assert result == expected


@pytest.mark.parametrize(
    "args",
    [
        [],  # missing required 'username'
        ["--username"],  # missing value
        ["--username", "x", "--retry", "invalid"],  # invalid integer
        ["--username", "x", "--verbose", "notabool"],  # invalid boolean
    ],
)
def test_invalid_inputs(
    basic_definitions: Dict[str, ProjectInput],
    args: list[str],
) -> None:
    parser = InputsParser.from_inputs_definitions(basic_definitions)
    with pytest.raises(UserNotificationException):
        parser.parse_inputs(args)
