# authors: Lilly Gerlach, Anna-Lena Penk

from PeachBattlePolicy import PeachBattlePolicy
from PeachSelectionPolicy import PeachSelectionPolicy
from PeachTeamBuildPolicy import PeachTeamBuildPolicy
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor


class PeachCompetitor(Competitor):

    def __init__(self, name: str = "PeachCompetitor"):
        self.__name = name
        self.__battle_policy = PeachBattlePolicy()
        self.__selection_policy = PeachSelectionPolicy()
        self.__team_build_policy = PeachTeamBuildPolicy()

    @property
    def battlepolicy(self) -> BattlePolicy | None:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy | None:
        return self.__selection_policy

    @property
    def teambuildpolicy(self) -> TeamBuildPolicy | None:
        return self.__team_build_policy

    @property
    def name(self) -> str:
        return self.__name
