"""
Competitor class for VGC AI Competition 2026.
Combines Enhanced Greedy Battle Policy, Coverage Selection Policy, and Smart Team Build Policy.
"""
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor

from battle_policy import ChampionshipBattlePolicy
from selection_policy import CoverageSelectionPolicy
from team_build_policy import SmartTeamBuildPolicy


class DaehoCompetitor(Competitor):
    def __init__(self, name: str = "Daeho_AI"):
        self.__name = name
        self.__battle_policy = ChampionshipBattlePolicy()
        self.__selection_policy = CoverageSelectionPolicy()
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