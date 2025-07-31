from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor
from iceMonteBattlePolicy import IceMonteBattlePolicy
from iceMonteSelectionPolicy import IceMonteSelectionPolicy
from iceMonteTeamBuildPolicy import IceMonteTeamBuildPolicy


class IceMonteCompetitor(Competitor):
    def __init__(self, name: str = "IceMonte"):
        self.__name = name
        self.__battle_policy = IceMonteBattlePolicy()
        self.__selection_policy = IceMonteSelectionPolicy()
        self.__team_build_policy = IceMonteTeamBuildPolicy()

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
