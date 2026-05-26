from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine.team import Team

from strategy import identify_strategy


class StrategySelectionPolicy(SelectionPolicy):
    def __init__(self, plan_holder: list):
        self._plan_holder = plan_holder

    def decision(self, teams: tuple[Team, Team], max_size: int) -> SelectionCommand:
        my_team = teams[0].members
        enemy_team = teams[1].members
        n = len(my_team)

        plan = identify_strategy(my_team, enemy_team)
        ordered = plan.lead_idxs + plan.reserve_idxs
        remaining = [i for i in range(n) if i not in ordered]
        ordered.extend(remaining)
        return ordered[:min(max_size, n)]
