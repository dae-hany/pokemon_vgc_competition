from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor

from battle_policy import StrategyBattlePolicy
from selection_policy import StrategySelectionPolicy
from team_build_policy import SmartTeamBuildPolicy


class DaehoV2Competitor(Competitor):
    def __init__(self, name: str = "DaehoV2"):
        self.__name = name
        self._plan_holder = [None]
        self.__battle_policy = StrategyBattlePolicy(self._plan_holder)
        self.__selection_policy = StrategySelectionPolicy(self._plan_holder)
        self.__team_build_policy = SmartTeamBuildPolicy()

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
