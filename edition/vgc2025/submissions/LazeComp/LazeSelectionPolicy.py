from random import shuffle

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import Team


class LazeSelectionPolicy(SelectionPolicy):
    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        status_list = []

        for i in range(len(teams[0].members)):
            pokemon = teams[0].members[i]
            status_count = 0
            for j in range(len(pokemon.moves)):
                move = pokemon.moves[j]
                if move.status != 0:
                    status_count += 1
                status_list.append([i, status_count])

        result = [x[0] for x in sorted(status_list, key=lambda x: x[1], reverse=True)]
        return result
