from numpy.random import choice

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand, Status, TeamView
import random
from typing import Optional


class LazeBattlePolicy(BattlePolicy):

    def __init__(self,
                 switch_prob: float = .15):
        self.switch_prob = switch_prob

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:

        my_team = state.sides[0].team
        opponent_team = state.sides[1].team

        n_switches = len(my_team.reserve)
        n_targets = len(opponent_team.active)
        status_targets = [i for i, pokemon in enumerate(opponent_team.active) if pokemon.status == Status.NONE]
        cmds: list[BattleCommand] = []

        for i in range(len(my_team.active)):

            pokemon = my_team.active[i]
            highest_power_move = 0

            # If there are opponent Pokémon without a status condition, try to use a status move
            if len(status_targets) > 0:
                status_move = [i for i, move in enumerate(pokemon.battling_moves) if
                               move.constants.status != Status.NONE]
                if len(status_move) > 0:
                    cmds.append((status_move[0], status_targets[0]))
                    status_targets = status_targets[1:]
                    continue

            # Find highest Power Move in each pokemon:
            for j in range(len(pokemon.battling_moves)):
                move = pokemon.battling_moves[j]
                power = move.constants.base_power

                if power > highest_power_move:
                    highest_power_move = j

            target = choice(n_targets, p=[1 / n_targets] * n_targets)
            cmds.append((highest_power_move, target))

        return cmds
