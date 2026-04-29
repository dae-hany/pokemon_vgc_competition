"""
Competitor class for VGC AI Competition 2026.
Combines MCTS Battle Policy, Coverage Selection Policy, and Smart Team Build Policy.
"""
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor

from battle_policy import EnhancedBattlePolicy
from selection_policy import CoverageSelectionPolicy
from team_build_policy import SmartTeamBuildPolicy


class DaehoCompetitor(Competitor):
    """
    Competition entry for Battle Track + Championship Track.
    - Battle: MCTS with enhanced evaluation (time-budgeted)
    - Selection: Type-coverage-based team selection
    - Team Build: Type-analysis with EV/Nature optimization
    """

    def __init__(self, name: str = "Daeho_AI"):
        self.__name = name
        self.__battle_policy = EnhancedBattlePolicy(max_depth=1, max_moves=4)
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
