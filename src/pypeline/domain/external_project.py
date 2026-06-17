from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExternalProject:
    """
    A repository cloned into the project tree by a dependency-install step.

    Published to the data registry so consumers locate a dependency by name
    instead of hardcoding its install path, which lets the step choose the
    on-disk layout (for example a revision subdirectory) transparently.
    """

    #: Project name, as declared in the manifest.
    name: str
    #: Revision the project was checked out at (tag, branch, or commit).
    revision: str
    #: Absolute, resolved install location.
    path: Path
