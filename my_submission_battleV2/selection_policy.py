from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine.team import Team

from strategy import _pick_best_n


class StrategySelectionPolicy(SelectionPolicy):
    def __init__(self, plan_holder: list):
        self._plan_holder = plan_holder

    def decision(self, teams: tuple[Team, Team], max_size: int) -> SelectionCommand:
        my_team = teams[0].members
        enemy_team = teams[1].members
        n = len(my_team)
        return _pick_best_n(list(range(n)), my_team, enemy_team, n=min(max_size, n))
