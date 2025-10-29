from minimonBattlePolicy import GreedyBattlePolicy
from minimonSelectionPolicy import DiverseTypeSelectionPolicy
from minimonTeambuildPolicy import StrongestTeamBuildPolicy
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor


class minimon(Competitor):

    def __init__(self, name: str = "minimon"):
        self.__name = name
        self.__battle_policy = GreedyBattlePolicy()
        self.__selection_policy = DiverseTypeSelectionPolicy()
        self.__team_build_policy = StrongestTeamBuildPolicy()

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
