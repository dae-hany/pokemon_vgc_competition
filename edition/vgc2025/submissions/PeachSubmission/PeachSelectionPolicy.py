import numpy as np

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import BattleRuleParam
from vgc2.battle_engine import Team


class PeachSelectionPolicy(SelectionPolicy):
    """
    Policy that selects team members according to probable type advantage.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:

        # def array of scores
        type_score = np.zeros(len(teams[0].members))

        # for each of our pokemon calc overall type-advantage-score
        for i, pkm in enumerate(teams[0].members):
            for enemy in teams[1].members:
                # add entry of typechart to score
                pkm_types = pkm.species.types
                enemy_types = enemy.species.types

                for type in pkm_types:
                    for en_type in enemy_types:
                        type_score[i] += BattleRuleParam().DAMAGE_MULTIPLICATION_ARRAY[type][en_type]

        selected = []

        # choose pkm with 4 highest scores for team
        for i in range(max_size):
            max = np.argmax(type_score)
            selected.append(max)
            type_score[max] = -1

        return selected
