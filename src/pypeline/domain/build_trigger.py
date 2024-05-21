from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class BuildTriggerType(Enum):
    #: The build is triggered by a pull request
    PULL_REQUEST = auto()
    #: The build is triggered by a push to a branch
    BRANCH_UPDATE = auto()
    #: Local user build
    LOCAL = auto()


@dataclass
class BuildTrigger:
    #: The type of trigger
    type: BuildTriggerType
    #: The pull request ID
    pull_request_id: Optional[str] = None
    #: The branch where the changes are being merged
    target_branch_name: Optional[str] = None
    #: The branch where the changes are coming from
    source_branch_name: Optional[str] = None
    #: The name of the branch
    branch_name: Optional[str] = None

    def __post_init__(self):
        """Validate the build trigger."""
        if self.type == BuildTriggerType.PULL_REQUEST:
            if not self.pull_request_id:
                raise ValueError("Pull request ID is required for pull request build trigger")
            if not self.target_branch_name:
                raise ValueError("Target branch name is required for pull request build trigger")
            if not self.source_branch_name:
                raise ValueError("Source branch name is required for pull request build trigger")
        elif self.type == BuildTriggerType.BRANCH_UPDATE:
            if not self.branch_name:
                raise ValueError("Branch name is required for branch update build trigger")

    @property
    def is_pull_request(self) -> bool:
        return self.type == BuildTriggerType.PULL_REQUEST
