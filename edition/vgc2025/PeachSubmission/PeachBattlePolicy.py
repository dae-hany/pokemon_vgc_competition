from itertools import product
from typing import Optional

import numpy as np
from numpy.random import choice

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand, TeamView, calculate_damage, BattleRuleParam


class PeachBattlePolicy(BattlePolicy):

    def __init__(self, params: BattleRuleParam = BattleRuleParam()):
        self.params = params

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:

        # select moves via greedy decision
        greedy_des = adapted_greedy_double_battle_decision(self.params, state)

        # check if any pkm are available for switch
        team = state.sides[0].team
        enemy_team = state.sides[1].team
        n_switches = len(team.reserve)

        if (n_switches > 0):

            # sum up the overall type advantage for available Pokemon
            score_res = np.zeros(len(team.reserve))

            for i, act_pk in enumerate(team.reserve):
                for ene_pk in enemy_team.active:
                    pkm_types = act_pk.types
                    enemy_types = ene_pk.types

                    for type in pkm_types:
                        for en_type in enemy_types:
                            score_res[i] += BattleRuleParam().DAMAGE_MULTIPLICATION_ARRAY[type][en_type]

            best_r = np.argmax(score_res)

            # swap in the pokemon with the most type advantage, if an active pokemon has low hp
            for i, act_pk in enumerate(team.active):
                if act_pk.hp <= 30:
                    greedy_des[i] = (-1, best_r)
                    break

        return greedy_des


def adapted_greedy_double_battle_decision(params: BattleRuleParam,
                                          state: State) -> list[BattleCommand]:
    attackers, defenders = state.sides[0].team.active, state.sides[1].team.active
    strategies = []
    for sources in product(list(range(len(attackers[0].battling_moves))),
                           list(range(len(attackers[1].battling_moves))) if len(attackers) > 1 else []):
        for targets in product(list(range(len(defenders))), list(range(len(defenders)))):
            damage, ko, hp = 0, 0, [d.hp for d in defenders]
            for i, (source, target) in enumerate(zip(sources, targets)):
                attacker, defender, move = attackers[i], defenders[target], attackers[i].battling_moves[source]
                if move.pp == 0 or move.disabled:
                    continue
                new_hp = max(0, hp[target] - calculate_damage(params, 0, move.constants, state, attacker, defender))
                damage += hp[target] - new_hp

                # weigh damage with accuracy of the move
                damage *= move.constants.accuracy

                # consider moves with status effects more heavily
                if move.constants.status != 0:
                    damage *= 1.2
                ko += int(new_hp == 0)
                hp[target] = new_hp
            strategies += [(ko, damage, sources, targets)]
    if len(strategies) == 0:
        return [(choice(len(a.battling_moves)), choice(len(defenders))) for a in attackers]
    best = max(strategies, key=lambda x: 1000 * x[0] + x[1])
    return list(zip(best[2], best[3]))
