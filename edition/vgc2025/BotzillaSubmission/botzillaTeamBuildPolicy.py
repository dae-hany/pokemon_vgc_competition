from numpy.random import choice, multinomial

from vgc2.agent import TeamBuildCommand
from vgc2.agent import TeamBuildPolicy
from vgc2.battle_engine.modifiers import Nature
from vgc2.battle_engine.pokemon import calculate_stats
from vgc2.meta import Meta
from vgc2.meta import Roster


class RandomTeamBuildPolicy(TeamBuildPolicy):
    """
    random team builder.
    """

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        ivs = (31,) * 6
        ids = choice(len(roster), 3, False)
        cmds: TeamBuildCommand = []
        for i in range(len(ids)):
            n_moves = len(roster[i].moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))
            evs = tuple(multinomial(510, [1 / 6] * 6, size=1)[0])
            nature = Nature(choice(len(Nature), 1, False))
            cmds += [(i, evs, ivs, nature, moves)]
        return cmds


class EducatedTeamBuildPolicy(TeamBuildPolicy):

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        cmds: TeamBuildCommand = []
        ivs = (31,) * 6

        # sort roster by best overall stats (not base stats)
        indexed_stats = []

        for i, pokemon in enumerate(roster):
            stats = calculate_stats(pokemon.base_stats, level=100)
            indexed_stats.append((i, pokemon, stats))

        sorted_stats = sorted(indexed_stats, key=lambda x: sum(x[2]), reverse=True)
        top_x = sorted_stats[:max_team_size]  # take top x best overall stats pkmn from roster

        # chosen = np.random.choice(top_10, max_team_size, replace=False)

        for original_index, pokemon, _ in top_x:
            n_moves = len(pokemon.moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), replace=False))
            evs = tuple(multinomial(510, [1 / 6] * 6, size=1)[0])
            nature = Nature(choice(len(Nature), 1, replace=False))
            cmds += [(original_index, evs, ivs, nature, moves)]
        return cmds
