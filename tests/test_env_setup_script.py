from pathlib import Path
from typing import Dict
from unittest.mock import Mock, patch

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


@patch("platform.system")
def test_setup_env_script_on_windows(mock_platform: Mock, execution_context: Mock) -> None:
    mock_platform.return_value = "Windows"
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("KEY1=value1\nKEY2=")
    execution_context.install_dirs = [Path("/path/to/dir1"), Path("path/dir2")]
    execution_context.env_vars = {"KEY3": "value1"}
    execution_context.get_input.return_value = None

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()

    assert execution_context.env_vars == {
        "KEY1": "value1",
        "KEY2": "",
        "KEY3": "value1",
    }
    # On Windows, should generate only bat and ps1 scripts
    for script_name in ["env_setup.bat", "env_setup.ps1"]:
        script_file = generator.output_dir / script_name
        assert script_file.exists()
        content = script_file.read_text()
        assert all(keyword in content for keyword in ["dir1", "dir2", "KEY1", "KEY2", "KEY3"])
    # Should NOT generate sh script on Windows by default
    sh_script = generator.output_dir / "env_setup.sh"
    assert not sh_script.exists()
    # get_outputs should return only the generated scripts
    outputs = generator.get_outputs()
    assert len(outputs) == 2
    assert generator.output_dir / "env_setup.bat" in outputs
    assert generator.output_dir / "env_setup.ps1" in outputs


@patch("platform.system")
def test_setup_env_script_on_unix(mock_platform: Mock, execution_context: Mock) -> None:
    mock_platform.return_value = "Linux"
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("KEY1=value1\nKEY2=")
    execution_context.install_dirs = [Path("/path/to/dir1"), Path("path/dir2")]
    execution_context.env_vars = {"KEY3": "value1"}
    execution_context.get_input.return_value = None

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()

    assert execution_context.env_vars == {
        "KEY1": "value1",
        "KEY2": "",
        "KEY3": "value1",
    }
    # On Unix, should generate only sh script
    sh_script = generator.output_dir / "env_setup.sh"
    assert sh_script.exists()
    content = sh_script.read_text()
    assert all(keyword in content for keyword in ["dir1", "dir2", "KEY1", "KEY2", "KEY3"])
    # Should NOT generate Windows scripts on Unix by default
    assert not (generator.output_dir / "env_setup.bat").exists()
    assert not (generator.output_dir / "env_setup.ps1").exists()
    # get_outputs should return only the generated script
    outputs = generator.get_outputs()
    assert len(outputs) == 1
    assert sh_script in outputs


@patch("platform.system")
def test_generate_all_scripts_on_windows(mock_platform: Mock, execution_context: Mock) -> None:
    mock_platform.return_value = "Windows"
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("KEY1=value1")
    execution_context.install_dirs = []
    execution_context.env_vars = {}
    execution_context.get_input.return_value = True

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()

    # With generate-all=true on Windows, should generate all three scripts
    for script_name in ["env_setup.bat", "env_setup.ps1", "env_setup.sh"]:
        script_file = generator.output_dir / script_name
        assert script_file.exists(), f"{script_name} should exist with generate-all=true"
    # get_outputs should return all three scripts
    outputs = generator.get_outputs()
    assert len(outputs) == 3


@patch("platform.system")
def test_generate_all_scripts_on_unix(mock_platform: Mock, execution_context: Mock) -> None:
    mock_platform.return_value = "Darwin"
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("KEY1=value1")
    execution_context.install_dirs = []
    execution_context.env_vars = {}
    execution_context.get_input.return_value = True

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()

    # With generate-all=true on Unix, should generate all three scripts
    for script_name in ["env_setup.bat", "env_setup.ps1", "env_setup.sh"]:
        script_file = generator.output_dir / script_name
        assert script_file.exists(), f"{script_name} should exist with generate-all=true"
    # get_outputs should return all three scripts
    outputs = generator.get_outputs()
    assert len(outputs) == 3


@patch("platform.system")
def test_sh_script_content(mock_platform: Mock, execution_context: Mock) -> None:
    mock_platform.return_value = "Linux"
    env_file = execution_context.project_root_dir / ".env"
    env_file.write_text("TEST_VAR=test_value")
    execution_context.install_dirs = [Path("/usr/local/bin")]
    execution_context.env_vars = {}
    execution_context.get_input.return_value = None

    generator = GenerateEnvSetupScript(execution_context, execution_context.project_root_dir)
    generator.run()

    sh_script = generator.output_dir / "env_setup.sh"
    content = sh_script.read_text()
    # Verify bash shebang and export statements
    assert "#!/bin/bash" in content
    assert "export TEST_VAR='test_value'" in content
    assert "export PATH='/usr/local/bin':\"$PATH\"" in content
