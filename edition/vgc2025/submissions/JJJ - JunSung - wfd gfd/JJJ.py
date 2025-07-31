from typing import List, Optional, Tuple

import numpy as np

from vgc2.agent import SelectionPolicy, SelectionCommand, BattlePolicy
from vgc2.battle_engine import BattleCommand
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.game_state import State
from vgc2.battle_engine.modifiers import Stat, Category
from vgc2.battle_engine.move import Move
from vgc2.battle_engine.pokemon import Pokemon, BattlingPokemon
from vgc2.battle_engine.team import Team
from vgc2.battle_engine.view import TeamView

DAMAGE_MULTIPLICATION_ARRAY = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
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
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
]


def compute_defensive_multiplier(p: Pokemon) -> float:
    hp_ratio = p.stats[Stat.MAX_HP] / 402
    def_ratio = p.stats[Stat.DEFENSE] / 257
    spd_ratio = p.stats[Stat.SPECIAL_DEFENSE] / 257
    return hp_ratio * def_ratio * spd_ratio


def estimate_damage_ratio(attacker: Pokemon, defender: Pokemon, move: Move) -> float:
    if move.category not in (Category.PHYSICAL, Category.SPECIAL):
        return 0.0

    atk_stat = (attacker.stats[Stat.ATTACK]
                if move.category == Category.PHYSICAL
                else attacker.stats[Stat.SPECIAL_ATTACK])
    def_stat = (defender.stats[Stat.DEFENSE]
                if move.category == Category.PHYSICAL
                else defender.stats[Stat.SPECIAL_DEFENSE])

    base_power = move.base_power + 12 * move.priority - 6
    stab = 1.5 if move.pkm_type in attacker.species.types else 1.0
    type_mul = 1.0
    for dt in defender.species.types:
        type_mul *= DAMAGE_MULTIPLICATION_ARRAY[move.pkm_type][dt]

    level = 100
    dmg = int((2 * level / 5) + 2)
    dmg = int(dmg * base_power)
    dmg = int(dmg * atk_stat / def_stat)
    dmg = int(dmg / 50) + 2
    final = int(dmg * stab * type_mul)
    return final / defender.stats[Stat.MAX_HP]


def estimate_damage_ratio_from_battlers(
        attacker: BattlingPokemon,
        defender: BattlingPokemon,
        move: Move
) -> float:
    return estimate_damage_ratio(attacker.constants,
                                 defender.constants,
                                 move.constants)


def score_best_move_attacker(attacker: Pokemon, defender: Pokemon) -> float:
    return max(
        (estimate_damage_ratio(attacker, defender, mv)
         for mv in attacker.moves),
        default=0.0
    )


def score_stats_by_priority(stats: Tuple[int], stat_weights: dict[Stat, float]) -> float:
    return sum(stats[s] * w for s, w in stat_weights.items())


def score_attacker(attacker: Pokemon, enemy_team: List[Pokemon]) -> float:
    total_damage = sum(
        score_best_move_attacker(attacker, other)
        for other in enemy_team
    )
    stat_score = compute_defensive_multiplier(attacker) * 0.42
    return 1.07 * total_damage + stat_score


def select_best_n_attackers_balanced(
        pokemon_list: List[Pokemon],
        enemy_team: List[Pokemon],
        n: int,
) -> List[Pokemon]:
    m = len(pokemon_list)
    k = len(enemy_team)

    damage_matrix = np.zeros((m, k), dtype=float)
    for i, atk in enumerate(pokemon_list):
        for j, dfn in enumerate(enemy_team):
            damage_matrix[i, j] = score_best_move_attacker(atk, dfn)

    score_vec = np.array([
        score_attacker(p, enemy_team)
        for p in pokemon_list
    ], dtype=float)

    selected = []
    first_idx = int(np.argmax(score_vec))
    selected.append(first_idx)
    coverage = damage_matrix[first_idx].copy()
    candidates = set(range(m)) - {first_idx}

    for _ in range(1, min(n, m)):
        old_range = coverage.max() - coverage.min()
        best_i, best_val = None, -np.inf

        for i in candidates:
            new_cov = coverage + damage_matrix[i]
            new_range = new_cov.max() - new_cov.min()
            delta_range = old_range - new_range
            sc = score_vec[i]
            val = 1.25 * delta_range + 0.74 * sc
            if val > best_val:
                best_val, best_i = val, i

        selected.append(best_i)
        coverage += damage_matrix[best_i]
        candidates.remove(best_i)

    return [pokemon_list[i] for i in selected]


class JJJ_selectionPolicy(SelectionPolicy):
    def decision(
            self,
            teams: Tuple[Team, Team],
            max_size: int
    ) -> SelectionCommand:
        my_team, enemy = teams[0].members, teams[1].members
        atk_candidates = [p for p in my_team]
        attackers = select_best_n_attackers_balanced(
            pokemon_list=atk_candidates,
            enemy_team=enemy,
            n=max_size
        )
        atk_idxs = [my_team.index(p) for p in attackers]
        return atk_idxs


def attacker_single_greedy(
        params: BattleRuleParam,
        state: State
) -> List[tuple[int, int]]:
    atk = state.sides[0].team.active[0]
    defenders = [d for d in state.sides[1].team.active if d is not None]
    if not defenders:
        return [(0, 0)]

    best, best_cmd = -1.0, (0, 0)
    for di, d in enumerate(defenders):
        for mi, mv in enumerate(atk.battling_moves):
            if mv.pp == 0 or mv.disabled or mv.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            ratio = estimate_damage_ratio_from_battlers(atk, d, mv)
            if ratio > best:
                best, best_cmd = ratio, (mi, di)
    return [best_cmd]


def attacker_duo_focus_fire(
        params: BattleRuleParam,
        state: State
) -> List[tuple[int, int]]:
    atks = state.sides[0].team.active
    defenders = [d for d in state.sides[1].team.active if d is not None]
    if not defenders:
        return [(0, 0), (0, 0)]

    best, best_cmds = -1.0, [(0, 0), (0, 0)]
    for di, d in enumerate(defenders):
        for i1, mv1 in enumerate(atks[0].battling_moves):
            if mv1.pp == 0 or mv1.disabled or mv1.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            for i2, mv2 in enumerate(atks[1].battling_moves):
                if mv2.pp == 0 or mv2.disabled or mv2.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                    continue
                total = (
                        estimate_damage_ratio_from_battlers(atks[0], d, mv1) +
                        estimate_damage_ratio_from_battlers(atks[1], d, mv2)
                )
                if total > best:
                    best, best_cmds = total, [(i1, di), (i2, di)]
    return best_cmds


class JJJ_BattlePolicy(BattlePolicy):
    def __init__(self, params: BattleRuleParam = BattleRuleParam()):
        self.params = params

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        alive_0 = [p for p in state.sides[0].team.active if p is not None]
        if len(alive_0) == 1:
            return attacker_single_greedy(self.params, state)
        return attacker_duo_focus_fire(self.params, state)
