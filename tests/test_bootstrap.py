import sys
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from pypeline.bootstrap.run import (
    BootstrapConfig,
    CreateBootstrapEnvironment,
    CreateVirtualEnvironment,
    PyPiSource,
    PyPiSourceParser,
    instantiate_os_specific_venv,
)


def test_pip_configure(tmp_path: Path) -> None:
    # Arrange
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)

    # Act
    my_venv = instantiate_os_specific_venv(venv_dir)
    my_venv.pip_configure("https://my.pypi.org/simple/stable")

    # Assert
    pip_ini = venv_dir / ("pip.ini" if sys.platform.startswith("win32") else "pip.conf")
    assert pip_ini.exists()
    assert (
        pip_ini.read_text()
        == """\
[global]
index-url = https://my.pypi.org/simple/stable
"""
    )

    # Act: call item under test again with different index-url and verify_ssl=False
    my_venv.pip_configure("https://some.other.pypi.org/simple/stable", False)

    # Assert
    assert (
        pip_ini.read_text()
        == """\
[global]
index-url = https://some.other.pypi.org/simple/stable
cert = false
"""
    )


def test_gitignore_configure(tmp_path: Path) -> None:
    # Arrange
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)

    # Act
    my_venv = instantiate_os_specific_venv(venv_dir)
    my_venv.gitignore_configure()

    # Assert
    gitignore = venv_dir / ".gitignore"
    assert gitignore.exists()
    assert gitignore.read_text() == "*\n"


@pytest.mark.parametrize(
    "toml_content, section_name, expected_source",
    [
        # Poetry style
        pytest.param(
            """
[tool.poetry.source]
name = "my_pypi"
url = "https://pypi.org/simple"
verify_ssl = true # Extra key should be ignored
""",
            "tool.poetry.source",
            PyPiSource(name="my_pypi", url="https://pypi.org/simple"),
            id="poetry_source",
        ),
        # Pipfile style (double brackets, different section name)
        pytest.param(
            """
[[source]]
name = "pipfile_pypi"
url = "https://pipfile.org/simple"
""",
            "source",
            PyPiSource(name="pipfile_pypi", url="https://pipfile.org/simple"),
            id="pipfile_source",
        ),
        # UV style (double brackets, different section name)
        pytest.param(
            """
[[tool.uv.index]]
name = "uv_pypi"
url = "https://uv.org/simple"
""",
            "tool.uv.index",
            PyPiSource(name="uv_pypi", url="https://uv.org/simple"),
            id="uv_index",
        ),
        # Arbitrary section name, valid content
        pytest.param(
            """
[my.custom.repo]
name = "custom_repo"
url = "https://custom.com/repo"
""",
            "my.custom.repo",
            PyPiSource(name="custom_repo", url="https://custom.com/repo"),
            id="custom_section_name",
        ),
        # Multiple sections, only one valid source
        pytest.param(
            """
[tool.poetry]
name = "my_package"
version = "0.1.0"

[[tool.uv.index]]
name = "the_correct_one"
url = "https://correct.com/pypi"

[tool.pytest.ini_options]
minversion = "6.0"
""",
            "tool.uv.index",
            PyPiSource(name="the_correct_one", url="https://correct.com/pypi"),
            id="multiple_sections_one_valid",
        ),
        # Section with quoted values (double quotes are stripped, single quotes are not)
        pytest.param(
            """
[source]
name = "quoted_pypi"
url = "https://quoted.org/simple"
""",
            "source",
            PyPiSource(name="quoted_pypi", url="https://quoted.org/simple"),
            id="quoted_values",
        ),
        pytest.param(
            """
[tool.poetry]
name = "not_a_source_section"
version = "1.0"
""",
            "tool.poetry.source",
            None,
            id="irrelevant_section",
        ),
    ],
)
def test_find_pypi_source_in_content(toml_content: str, section_name: str, expected_source: PyPiSource | None) -> None:
    # Act
    pypi_source = PyPiSourceParser.from_toml_content(toml_content, section_name)

    # Assert
    assert pypi_source == expected_source


def test_pypi_source_from_pipfile(tmp_path: Path) -> None:
    # Arrange: Create project directory
    project_dir = tmp_path / "some_project"
    project_dir.mkdir(parents=True)

    # Act: No config files exist
    pypi_source = PyPiSourceParser.from_pyproject(project_dir)
    # Assert: Should find nothing
    assert pypi_source is None

    # Arrange: Add Pipfile with a source
    pipfile = project_dir / "Pipfile"
    pipfile.write_text(
        """
[[source]]
name = "pipfile_pypi"
url = "https://pipfile.org/simple"
verify_ssl = true
"""
    )
    # Act: Only Pipfile exists
    pypi_source = PyPiSourceParser.from_pyproject(project_dir)
    # Assert: Should find the source from Pipfile
    assert pypi_source == PyPiSource(name="pipfile_pypi", url="https://pipfile.org/simple")


def test_pypi_source_from_pyproject_toml(tmp_path: Path) -> None:
    # Arrange: Create project directory
    project_dir = tmp_path / "some_project"
    project_dir.mkdir(parents=True)

    # Act: No config files exist
    pypi_source = PyPiSourceParser.from_pyproject(project_dir)
    # Assert: Should find nothing
    assert pypi_source is None

    # Arrange: Add pyproject.toml with tool.poetry.source section
    pyproject_toml = project_dir / "pyproject.toml"
    pyproject_toml.write_text(
        """
[tool.otherstuff]
key = "value"

# This should be found because it matches tool.poetry.source
[tool.poetry.source]
name = "poetry_pypi_in_pyproject"
url = "https://poetry-pyproject.org/simple"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""
    )
    # Act
    pypi_source = PyPiSourceParser.from_pyproject(project_dir)
    # Assert
    assert pypi_source == PyPiSource(name="poetry_pypi_in_pyproject", url="https://poetry-pyproject.org/simple")


@pytest.mark.parametrize(
    "package_manager, python_version, expected_calls",
    [
        pytest.param(
            "uv>=0.6",
            "3.13",
            [
                ("UV_PYTHON", "3.13"),
                ("UV_MANAGED_PYTHON", "false"),
                ("UV_NO_PYTHON_DOWNLOADS", "true"),
            ],
            id="uv_with_version",
        ),
        pytest.param(
            "uv>=0.6",
            "3.11.5",
            [
                ("UV_PYTHON", "3.11.5"),
                ("UV_MANAGED_PYTHON", "false"),
                ("UV_NO_PYTHON_DOWNLOADS", "true"),
            ],
            id="uv_with_patch_version",
        ),
        pytest.param(
            "poetry>=2.0",
            "3.13",
            [
                ("POETRY_VIRTUALENVS_PREFER_ACTIVE_PYTHON", "false"),
                ("POETRY_VIRTUALENVS_USE_POETRY_PYTHON", "true"),
            ],
            id="poetry_with_version",
        ),
    ],
)
def test_ensure_correct_python_version_sets_env_vars(
    tmp_path: Path,
    package_manager: str,
    python_version: str,
    expected_calls: list[tuple[str, str]],
) -> None:
    """Test that _ensure_correct_python_version sets the correct environment variables."""
    # Arrange
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)

    config = BootstrapConfig(
        python_version=python_version,
        package_manager=package_manager,
    )

    bootstrap_env = CreateBootstrapEnvironment(config, project_dir)
    create_venv = CreateVirtualEnvironment(project_dir, bootstrap_env)

    # Mock the helper method to avoid actual environment modification
    mock_set_env = Mock()
    with patch.object(create_venv, "_set_env_var", mock_set_env):
        # Act
        create_venv._ensure_correct_python_version()

        # Assert: Verify _set_env_var was called with the right arguments
        expected_call_objects = [call(key, value) for key, value in expected_calls]
        mock_set_env.assert_has_calls(expected_call_objects)
        assert mock_set_env.call_count == len(expected_calls)
