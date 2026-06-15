import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from pypeline.domain.execution_context import ExecutionContext
from pypeline.steps.env_setup_script import GenerateEnvSetupScript
from pypeline.steps.resolve_license import ResolveLicenseServer


@pytest.fixture
def license_config(execution_context: Mock) -> Path:
    config = {
        "timezones": {
            "germany": ["W. Europe Standard Time", "Central European Standard Time", "CET"],
            "pune": ["India Standard Time"],
            "shanghai": ["China Standard Time"],
            "romania": ["GTB Standard Time", "E. Europe Standard Time", "EET"],
        },
        "servers": {
            "germany": {"TASKING_LICENSE_SERVER": "1234@license-de.example.com"},
            "pune": {"TASKING_LICENSE_SERVER": "1234@license-pune.example.com"},
            "shanghai": {"TASKING_LICENSE_SERVER": "1234@license-sha.example.com"},
            "romania": {"TASKING_LICENSE_SERVER": "1234@license-ro.example.com"},
            "default": {"TASKING_LICENSE_SERVER": "1234@license-de.example.com"},
        },
    }
    config_file = execution_context.project_root_dir / "license_servers.json"
    config_file.write_text(json.dumps(config))
    return config_file


@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_resolve_matching_site(mock_tz: Mock, execution_context: Mock, license_config: Path) -> None:
    mock_tz.return_value = "India Standard Time"
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})
    step.run()

    execution_context.add_env_vars.assert_called_once_with({"TASKING_LICENSE_SERVER": "1234@license-pune.example.com"})


@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_resolve_fallback_to_default(mock_tz: Mock, execution_context: Mock, license_config: Path) -> None:
    mock_tz.return_value = "Eastern Standard Time"
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})
    step.run()

    execution_context.add_env_vars.assert_called_once_with({"TASKING_LICENSE_SERVER": "1234@license-de.example.com"})


@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_resolve_no_match_no_default_raises_error(mock_tz: Mock, execution_context: Mock) -> None:
    config = {
        "timezones": {"germany": ["W. Europe Standard Time"]},
        "servers": {"germany": {"TASKING_LICENSE_SERVER": "1234@license-de.example.com"}},
    }
    config_file = execution_context.project_root_dir / "license_servers.json"
    config_file.write_text(json.dumps(config))

    mock_tz.return_value = "Eastern Standard Time"
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})

    with pytest.raises(UserNotificationException, match="No license server configured for timezone"):
        step.run()


def test_resolve_config_file_not_found_raises_error(execution_context: Mock) -> None:
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "nonexistent.json"})

    with pytest.raises(UserNotificationException, match="License config file not found"):
        step.run()


@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_resolve_germany_with_cet(mock_tz: Mock, execution_context: Mock, license_config: Path) -> None:
    mock_tz.return_value = "CET"
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})
    step.run()

    execution_context.add_env_vars.assert_called_once_with({"TASKING_LICENSE_SERVER": "1234@license-de.example.com"})


@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_update_execution_context_restores_cached(mock_tz: Mock, execution_context: Mock, license_config: Path) -> None:
    mock_tz.return_value = "India Standard Time"
    execution_context.env_vars = {}

    step = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})
    step.run()

    execution_context.add_env_vars.reset_mock()

    step2 = ResolveLicenseServer(execution_context, None, {"license_config": "license_servers.json"})
    step2.update_execution_context()

    execution_context.add_env_vars.assert_called_once_with({"TASKING_LICENSE_SERVER": "1234@license-pune.example.com"})


@patch("platform.system")
@patch.object(ResolveLicenseServer, "_detect_timezone")
def test_resolved_license_flows_into_env_setup_scripts(mock_tz: Mock, mock_platform: Mock, tmp_path: Path) -> None:
    mock_tz.return_value = "India Standard Time"
    mock_platform.return_value = "Windows"

    config = {
        "timezones": {"pune": ["India Standard Time"]},
        "servers": {"pune": {"TASKING_LICENSE_SERVER": "1234@license-pune.example.com"}},
    }
    (tmp_path / "license_servers.json").write_text(json.dumps(config))

    context = ExecutionContext(project_root_dir=tmp_path)

    resolve_step = ResolveLicenseServer(context, None, {"license_config": "license_servers.json"})
    resolve_step.run()

    env_step = GenerateEnvSetupScript(context, None)
    env_step.run()

    for script_name in ["env_setup.bat", "env_setup.ps1"]:
        content = (env_step.output_dir / script_name).read_text()
        assert "TASKING_LICENSE_SERVER" in content
        assert "1234@license-pune.example.com" in content
