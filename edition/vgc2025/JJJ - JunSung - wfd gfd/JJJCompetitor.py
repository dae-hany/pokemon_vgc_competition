from JJJ import JJJ_BattlePolicy, JJJ_selectionPolicy
from JJJTeamPolicy import JJJ_TeamBuildPolicy
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor


class JJJ_Competitor(Competitor):

    def __init__(self, name: str = "JJJ"):
        self.__name = name
        self.__battle_policy = JJJ_BattlePolicy()
        self.__selection_policy = JJJ_selectionPolicy()
        self.__team_build_policy = JJJ_TeamBuildPolicy()

    @property
    def name(self) -> str:
        return self.__name

    @property
    def battle_policy(self) -> BattlePolicy:
        return self.__battle_policy

    @property
    def selection_policy(self) -> SelectionPolicy:
        return self.__selection_policy

    @property
    def team_build_policy(self) -> TeamBuildPolicy:
        return self.__team_build_policy
