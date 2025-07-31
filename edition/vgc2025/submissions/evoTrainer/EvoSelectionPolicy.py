from random import shuffle

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import Team


class BasicSelectionPolicy(SelectionPolicy):
    """
    Policy that selects team members in order.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        return list(set(range(len(teams[0].members))))[:max_size]


class RandomSelectionPolicy(SelectionPolicy):
    """
    Policy that selects team members in a random order.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        ids = list(set(range(len(teams[0].members))))[:max_size]
        shuffle(ids)
        return ids
