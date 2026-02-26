import numpy as np
from numpy.random import choice, multinomial
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature, Stat
from vgc2.balance.meta import Meta, Roster


class LazeTeamBuildPolicy(TeamBuildPolicy):

    def __init__(self, params: BattleRuleParam = BattleRuleParam()):
        self.DAMAGE_MULTIPLICATION_ARRAY = params.DAMAGE_MULTIPLICATION_ARRAY

    def decision(self, roster: Roster, meta: Meta | None, max_team_size: int, max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:

        ivs = (31,) * 6
        indexed_roster = list(enumerate(roster))

        for hp_threshold in [140, 120, 100, 0]:  # Letzter Fallback: Keine HP-Grenze
            hp_filtered_roster_with_indices = [(index, pokemon) for index, pokemon in indexed_roster if
                                               pokemon.base_stats[Stat.MAX_HP] > hp_threshold]
            if len(hp_filtered_roster_with_indices) >= 4:
                break

        hp_filtered_roster = [pokemon for _, pokemon in hp_filtered_roster_with_indices]

        # Type-Fitness Calculation
        typeCount = np.zeros(18)
        typeFitness = np.zeros(18)
        for pokemon in roster:
            for t in pokemon.types:
                typeCount[t] += 1
        for pkmn in hp_filtered_roster:
            for pkmn2 in roster:
                for type1 in pkmn.types:
                    for type2 in pkmn2.types:
                        typeFitness[type1] += (self.DAMAGE_MULTIPLICATION_ARRAY[type1][type2] - 1) * typeCount[type2]

        avgTypeFitness = int(sum(typeFitness) / len(typeFitness))

        typeFitness_filtered = [(index, pokemon) for index, pokemon in hp_filtered_roster_with_indices
                                if any(typeFitness[t] > avgTypeFitness for t in pokemon.types)]
        if len(typeFitness_filtered) < 4:
            typeFitness_filtered = hp_filtered_roster_with_indices  # Fallback: No Typ-Fitness-Restriction

        move_filtered = [index for index, pokemon in typeFitness_filtered
                         if any(move.pkm_type in pokemon.types and move.base_power > 0 for move in pokemon.moves)]
        if len(move_filtered) < 4:
            move_filtered = [index for index, _ in typeFitness_filtered]  # Fallback: No Move-Restriction

        while len(move_filtered) < 4:
            remaining_indices = set(range(len(roster))) - set(move_filtered)
            if not remaining_indices:
                break
            move_filtered.append(choice(list(remaining_indices)))

        best_indices = sorted(move_filtered, key=lambda i: sum(move.base_power for move in roster[i].moves),
                              reverse=True)[:4]

        cmds: TeamBuildCommand = []
        for i in best_indices:
            n_moves = len(roster[i].moves)
            # print(f"N_Moves: {n_moves}")
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))
            # print(f"Moves: {moves}")
            evs = tuple(multinomial(510, [1 / 6] * 6, size=1)[0])
            # evs = (0, 510, 0, 0, 0, 0)
            # print(f"EVS: {evs}")
            nature = Nature(choice(len(Nature), 1, False))
            # print(f"Nature: {nature}")
            cmds += [(i, evs, ivs, nature, moves)]
        return cmds
