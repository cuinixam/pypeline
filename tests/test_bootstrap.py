import sys
from pathlib import Path

import pytest

from pypeline.bootstrap.run import (
    CreateVirtualEnvironment,
    PyPiSource,
    PyPiSourceParser,
)


def test_pip_configure(tmp_path: Path) -> None:
    # Arrange
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)

    # Act
    my_venv = CreateVirtualEnvironment.instantiate_os_specific_venv(venv_dir)
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
    my_venv = CreateVirtualEnvironment.instantiate_os_specific_venv(venv_dir)
    my_venv.gitignore_configure()

    # Assert
    gitignore = venv_dir / ".gitignore"
    assert gitignore.exists()
    assert gitignore.read_text() == "*\n"


@pytest.mark.parametrize(
    "toml_content, expected_source",
    [
        # Poetry style
        pytest.param(
            """
[tool.poetry.source]
name = "my_pypi"
url = "https://pypi.org/simple"
verify_ssl = true # Extra key should be ignored
""",
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
            PyPiSource(name="the_correct_one", url="https://correct.com/pypi"),
            id="multiple_sections_one_valid",
        ),
        # Section with quoted values
        pytest.param(
            """
[source]
name = "quoted_pypi"
url = 'https://quoted.org/simple'
""",
            PyPiSource(name="quoted_pypi", url="https://quoted.org/simple"),
            id="quoted_values",
        ),
        pytest.param(
            """
[tool.poetry]
name = "not_a_source_section"
version = "1.0"
""",
            None,
            id="irrelevant_section",
        ),
    ],
)
def test_find_pypi_source_in_content(toml_content: str, expected_source: PyPiSource | None) -> None:
    # Act
    pypi_source = PyPiSourceParser.find_pypi_source_in_content(toml_content)

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

    # Arrange: Add pyproject.toml with a *different* source (using uv style)
    pyproject_toml = project_dir / "pyproject.toml"
    pyproject_toml.write_text(
        """
[tool.otherstuff]
key = "value"

# This should be found because it has name and url
[[tool.uv.index]]
name = "uv_pypi_in_pyproject"
url = "https://uv-pyproject.org/simple"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""
    )
    # Act
    pypi_source = PyPiSourceParser.from_pyproject(project_dir)
    # Assert
    assert pypi_source == PyPiSource(name="uv_pypi_in_pyproject", url="https://uv-pyproject.org/simple")
