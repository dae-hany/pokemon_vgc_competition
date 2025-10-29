from StocKarpadorBattlePolicy import MonteCarloBattlePolicy
from StocKarpadorSelectionPolicy import HeuristicSelectionPolicy
from StocKarpadorTeamBuildPolicy import HeuristicTeamBuildPolicy
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor


class StocKarpadorCompetitor(Competitor):
    """Competitor by Fidelio Luc Reichard and Malte Rost"""

    def __init__(self, name: str = "StocKarpador"):
        self.__name = name
        self.__battle_policy = MonteCarloBattlePolicy()
        self.__selection_policy = HeuristicSelectionPolicy()
        self.__team_build_policy = HeuristicTeamBuildPolicy()

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
