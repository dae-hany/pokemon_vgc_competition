import EvoBattlePolicy as bp
import EvoSelectionPolicy as sp
from vgc2.agent import BattlePolicy, SelectionPolicy
from vgc2.competition import Competitor


class EvoCompetitor(Competitor):

    def __init__(self, name: str = "Evo"):
        self.__name = name
        self.__battle_policy = bp.EvoBattlePolicy()
        self.__selection_policy = sp.BasicSelectionPolicy()

    @property
    def battlepolicy(self) -> BattlePolicy | None:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy | None:
        return self.__selection_policy

    @property
    def name(self) -> str:
        return self.__name

    def plot_rule_usage(self, name):
        self.__battle_policy.show_rule_usage(name)
