import io
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from mashumaro.config import TO_DICT_ADD_OMIT_NONE_FLAG, BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.core.scoop_wrapper import ScoopWrapper

from ..domain.execution_context import ExecutionContext
from ..domain.pipeline import PipelineStep


@dataclass
class ScoopInstallExecutionInfo(DataClassJSONMixin):
    install_dirs: List[Path]

    class Config(BaseConfig):
        """Base configuration for JSON serialization with omitted None values."""

        code_generation_options: ClassVar[List[str]] = [TO_DICT_ADD_OMIT_NONE_FLAG]

    @classmethod
    def from_json_file(cls, file_path: Path) -> "ScoopInstallExecutionInfo":
        try:
            result = cls.from_dict(json.loads(file_path.read_text()))
        except Exception as e:
            output = io.StringIO()
            traceback.print_exc(file=output)
            raise UserNotificationException(output.getvalue()) from e
        return result

    def to_json_string(self) -> str:
        return json.dumps(self.to_dict(omit_none=True), indent=2)

    def to_json_file(self, file_path: Path) -> None:
        file_path.write_text(self.to_json_string())


def create_scoop_wrapper() -> ScoopWrapper:
    return ScoopWrapper()


class ScoopInstall(PipelineStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.execution_info = ScoopInstallExecutionInfo([])
        # One needs to keep track of the installed apps to get the required paths
        # even if the step does not need to run.
        self.execution_info_file = self.output_dir.joinpath("scoop_install_exec_info.json")

    def get_name(self) -> str:
        return self.__class__.__name__

    @property
    def install_dirs(self) -> List[Path]:
        return self.execution_info.install_dirs

    @property
    def scoop_file(self) -> Path:
        return self.project_root_dir.joinpath("scoopfile.json")

    def run(self) -> int:
        self.logger.debug(f"Run {self.get_name()} step. Output dir: {self.output_dir}")
        installed_apps = create_scoop_wrapper().install(self.scoop_file)
        self.logger.debug("Installed apps:")
        for app in installed_apps:
            self.logger.debug(f" - {app.name} ({app.version})")
            self.install_dirs.extend(app.get_all_required_paths())
        self.execution_info.to_json_file(self.execution_info_file)
        return 0

    def get_inputs(self) -> List[Path]:
        return [self.scoop_file]

    def get_outputs(self) -> List[Path]:
        return [self.execution_info_file, *self.install_dirs]

    def update_execution_context(self) -> None:
        install_dirs = ScoopInstallExecutionInfo.from_json_file(self.execution_info_file).install_dirs
        # Make the list unique and keep the order
        unique_paths = list(dict.fromkeys(install_dirs))
        # Update the install directories for the subsequent steps
        self.execution_context.add_install_dirs(unique_paths)
