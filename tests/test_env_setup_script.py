from pathlib import Path
from typing import Dict
from unittest.mock import Mock

import pytest

from pypeline.steps.env_setup_script import GenerateEnvSetupScript, read_dot_env_file


@pytest.mark.parametrize(
    "file_content,expected_output",
    [
        ("KEY1=value1\nKEY2= -1", {"KEY1": "value1", "KEY2": "-1"}),
        ("# This is a comment\nKEY=value\n\n# Another comment", {"KEY": "value"}),
        ("KEY='value with spaces'\nANOTHER=\"quoted\"", {"KEY": "value with spaces", "ANOTHER": "quoted"}),
        ("  SPACED_KEY = spaced_value  ", {"SPACED_KEY": "spaced_value"}),
    ],
)
def test_read_dot_env_file(file_content: str, expected_output: Dict[str, str], tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(file_content)

    result = read_dot_env_file(env_file)

    assert result == expected_output


def test_setup_env_script(execution_context: Mock) -> None:
    # Create a temporary .env file with some content
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("KEY1=value1\nKEY2=")
    # Add install directories in the execution context
    execution_context.install_dirs = [Path("/path/to/dir1"), Path("path/dir2")]

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()
    # Check if the generated script files exist
    for script_name in ["env_setup.bat", "env_setup.ps1"]:
        script_file = generator.output_dir / script_name
        assert script_file.exists()
        content = script_file.read_text()
        assert all(keyword in content for keyword in ["dir1", "dir2", "KEY1", "KEY2"])
