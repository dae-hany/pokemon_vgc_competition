from LazeBattlePolicy import LazeBattlePolicy
from LazeSelectionPolicy import LazeSelectionPolicy
from LazeTeamBuildPolicy import LazeTeamBuildPolicy
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor


class LazeCompetitor(Competitor):

    def __init__(self, name: str = "LazeCompetitor"):
        self.__name = name
        self.__battle_policy = LazeBattlePolicy()
        self.__selection_policy = LazeSelectionPolicy()
        self.__team_build_policy = LazeTeamBuildPolicy()

    @property
    def battle_policy(self) -> BattlePolicy | None:
        return self.__battle_policy

    @property
    def selection_policy(self) -> SelectionPolicy | None:
        return self.__selection_policy

    @property
    def team_build_policy(self) -> TeamBuildPolicy | None:
        return self.__team_build_policy

    @property
    def name(self) -> str:
        return self.__name

