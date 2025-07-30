import os.path
import warnings

from botzillaBattlePolicy import QTableBattlePolicy
from botzillaSelectionPolicy import BalancedStatSelectionPolicy
from botzillaTeamBuildPolicy import EducatedTeamBuildPolicy

from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.competition import Competitor
from vgc2.util.encoding import EncodeContext


class BotzillaCompetitor(Competitor):

    def __init__(self, name: str = "Botzilla"):
        self.__name = name
        script_dir = os.path.dirname(__file__)
        q_table_path = os.path.abspath(os.path.join(script_dir, "q_table.csv"))
        # q_table_path = os.path.abspath(os.path.join(script_dir, "..", "q_table.csv"))
        self.__battle_policy = QTableBattlePolicy(q_table_path, EncodeContext(), [10, 10])
        self.__selection_policy = BalancedStatSelectionPolicy()
        self.__team_build_policy = EducatedTeamBuildPolicy()

    @property
    def battle_policy(self) -> BattlePolicy | None:
        warnings.filterwarnings("ignore")  # suppress warnings due to missing column names when calling clf.predict()
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
