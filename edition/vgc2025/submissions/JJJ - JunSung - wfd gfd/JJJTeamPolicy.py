from typing import List

import numpy as np
from numpy.random import choice

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature, Type as PkmType, Category
from vgc2.balance.meta import Roster, Meta


def max_expected_damage_against_type(
        pokemon,
        target_type: PkmType,
        type_multiplier: np.ndarray,
) -> float:
    best = 0.0
    for move in pokemon.moves:

        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue

        if move.category == Category.PHYSICAL:
            A = pokemon.base_stats[1]
        else:
            A = pokemon.base_stats[3]

        P = move.base_power
        acc = move.accuracy

        stab = 1.5 if move.pkm_type in pokemon.types else 1.0

        eff = type_multiplier[move.pkm_type.value, target_type.value]

        raw = 0.84 * P * A / 1 + 2

        exp_dmg = acc * raw * stab * eff
        if exp_dmg > best:
            best = exp_dmg

    return best


def build_type_rank_matrix(
        roster: List,
        type_multiplier: np.ndarray,
) -> np.ndarray:
    n_types = type_multiplier.shape[0]
    n_pkm = len(roster)
    damage = np.zeros((n_types, n_pkm), dtype=float)
    for i in range(n_types):
        for j, pkm in enumerate(roster):
            damage[i, j] = max_expected_damage_against_type(pkm, PkmType(i), type_multiplier)
    rank = np.argsort(np.argsort(-damage, axis=1), axis=1) + 1
    return rank


def select_team(
        rank: np.ndarray,
        a: float,
        b: float,
        team_size: int,
) -> List[int]:
    n_types, n_pkm = rank.shape
    sum_ranks = rank.sum(axis=0)
    selected = []

    first = int(np.argmin(sum_ranks))
    selected.append(first)

    for _ in range(1, team_size):
        best_j, best_score = None, float('inf')
        for j in range(n_pkm):
            if j in selected:
                continue
            sr = sum_ranks[j]
            current = selected + [j]
            total_rank = rank[:, current].sum(axis=1)
            range_diff = total_rank.max() - total_rank.min()
            score = a * sr + b * range_diff
            if score < best_score:
                best_score = score
                best_j = j
        selected.append(best_j)
    return selected


class JJJ_TeamBuildPolicy(TeamBuildPolicy):
    def __init__(self, a: float = 0.45, b: float = 0.45):
        self.a = a
        self.b = b

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:

        roster_list: List = list(roster)

        high_hp = [p for p in roster_list if p.base_stats[0] >= 120]
        if len(high_hp) >= max_team_size:

            candidates = high_hp
        else:

            rest = [p for p in roster_list if p not in high_hp]
            candidates = high_hp + rest[: max_team_size - len(high_hp)]

        orig_idxs = [roster_list.index(p) for p in candidates]

        raw_array = [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
                     [1, .5, .5, 1, 2, 2, 1, 1, 1, 1, 1, 2, .5, 1, .5, 1, 2, 1, 1],
                     [1, 2, .5, 1, .5, 1, 1, 1, 2, 1, 1, 1, 2, 1, .5, 1, 1, 1, 1],
                     [1, 1, 2, .5, .5, 1, 1, 1, 0, 2, 1, 1, 1, 1, .5, 1, 1, 1, 1],
                     [1, .5, 2, 1, .5, 1, 1, .5, 2, .5, 1, .5, 2, 1, .5, 1, .5, 1, 1],
                     [1, .5, .5, 1, 2, .5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, .5, 1, 1],
                     [2, 1, 1, 1, 1, 2, 1, .5, 1, .5, .5, .5, 2, 0, 1, 2, 2, .5, 1],
                     [1, 1, 1, 1, 2, 1, 1, .5, .5, 1, 1, 1, .5, .5, 1, 1, 0, 2, 1],
                     [1, 2, 1, 2, .5, 1, 1, 2, 1, 0, 1, .5, 2, 1, 1, 1, 2, 1, 1],
                     [1, 1, 1, .5, 2, 1, 2, 1, 1, 1, 1, 2, .5, 1, 1, 1, .5, 1, 1],
                     [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, .5, 1, 1, 1, 1, 0, .5, 1, 1],
                     [1, .5, 1, 1, 2, 1, .5, .5, 1, .5, 2, 1, 1, .5, 1, 2, .5, .5, 1],
                     [1, 2, 1, 1, 1, 2, .5, 1, .5, 2, 1, 2, 1, 1, 1, 1, .5, 1, 1],
                     [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, 1, 1],
                     [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, .5, 0, 1],
                     [1, 1, 1, 1, 1, 1, .5, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, .5, 1],
                     [1, .5, .5, .5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, .5, 2, 1],
                     [1, .5, 1, 1, 1, 1, 2, .5, 1, 1, 1, 1, 1, 1, 2, 2, .5, 1, 1],
                     [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]
        type_mult = np.zeros((19, 19), dtype=float)
        for i in range(19):
            for j in range(19):
                type_mult[i, j] = raw_array[i][j]

        rank_matrix = build_type_rank_matrix(candidates, type_mult)

        rel_idxs = select_team(rank_matrix, self.a, self.b, max_team_size)

        selected_idxs = [orig_idxs[i] for i in rel_idxs]

        cmds: TeamBuildCommand = []
        for idx in selected_idxs:
            pkm = roster_list[idx]

            phy_sum = sum(m.base_power * pkm.base_stats[1]
                          for m in pkm.moves if m.category == Category.PHYSICAL)
            spc_sum = sum(m.base_power * pkm.base_stats[3]
                          for m in pkm.moves if m.category == Category.SPECIAL)

            if phy_sum > spc_sum:
                evs = (252, 168, 0, 84, 0, 6)
                nature = Nature.ADAMANT
            elif spc_sum > phy_sum:
                evs = (252, 84, 0, 168, 0, 6)
                nature = Nature.MODEST
            else:

                evs = (254, 128, 0, 128, 0, 0)
                nature = Nature.HASTY

            ivs = (31,) * 6

            move_indices = list(choice(len(pkm.moves), min(len(pkm.moves), max_pkm_moves), replace=False))
            cmds.append((idx, evs, ivs, nature, move_indices))

        return cmds
