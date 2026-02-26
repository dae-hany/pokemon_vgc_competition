import os

from monte_carlo_multi_process_battle_policy import (
    MonteCarloMultiProcessBattlePolicy,
)
from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.competition import Competitor


class S7Competitor(Competitor):
    def __init__(self, name: str = "Yamabuki"):
        self.__name = name
        self.__battle_policy = MonteCarloMultiProcessBattlePolicy(
            # The competition rule says "in the order of 100ms", so I set decision time as 500ms + overhead.
            decision_time=0.5,
            rollout_turns_greedy=2,
            rollout_turns_random=1,
            c_puct=0.5,
            model_path=os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "evaluation_model.pkl"
            ),
        )
        self.__selection_policy = RandomSelectionPolicy()
        self.__team_build_policy = RandomTeamBuildPolicy()

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
