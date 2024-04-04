"""
Used to run pypeline from the command line when run from this repository.

This is required because pypeline module is not visible when running from the repository.
"""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, Path(__file__).parent.parent.absolute().as_posix())
runpy.run_module("pypeline.main", run_name="__main__")
